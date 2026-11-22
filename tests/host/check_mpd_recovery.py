#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the prepared qcom_q6v5_mpd.c PD start/stop/recovery functions against a
host model of the remoteproc core (rproc_boot/rproc_shutdown refcounts, the
crash handler state machine, rproc_start not calling .stop on a failed .start).

  check_mpd_recovery.py PATH/drivers/remoteproc/qcom_q6v5_mpd.c [--expect-fail]

Exit 0 when every scenario passes (or, with --expect-fail, when at least one
fails: used to prove the scenarios detect the unpatched driver)."""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = ["q6_wcss_spawn_pd", "wcss_pd_start", "wcss_pd_stop", "wcss_pd_load", "q6_wcss_start"]
OPTIONAL = ["wcss_pd_put_rpd", "q6_wcss_recover_userpds"]


def function(src, name):
    m = re.search(r"^(?:static\s+)?(?:int|void)\s+" + name + r"\([^;{]*\)\s*\{", src, re.M)
    if not m:
        return None
    return src[m.start():src.index("\n}\n", m.end()) + 3]


def struct(src, name):
    m = re.search(r"^struct " + name + r" \{.*?^\};\n", src, re.M | re.S)
    if not m:
        raise SystemExit(f"missing struct {name}")
    return m.group(0)


HEADER = r"""
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef unsigned int u32; typedef unsigned char u8; typedef unsigned long phys_addr_t;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, v) ((x) = (v))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define HZ 100
#define msecs_to_jiffies(x) (x)
#define dev_err(d, ...) ((void)0)
#define MAX_UPD 3
#define UPD_SWID 0x12
enum { RPROC_OFFLINE, RPROC_SUSPENDED, RPROC_RUNNING, RPROC_CRASHED };
enum { RPROC_FATAL_ERROR = 1 };
struct work_struct { void (*fn)(struct work_struct *); int pending; };
#define INIT_WORK(w, f) ((w)->fn = (f))
#define system_long_wq 0
#define queue_work(wq, w) ((w)->pending = 1)
static void flush_work(struct work_struct *w) { if (w->pending) { w->pending = 0; w->fn(w); } }
#define cancel_work_sync(w) ((w)->pending = 0)
struct firmware { int unused; };
struct device { struct device *parent; void *drvdata; };
#define dev_get_drvdata(d) ((d)->drvdata)
struct rproc { int state, power, mid_recovery; void *priv; bool recovery_disabled;
               struct work_struct crash_handler; const char *name, *firmware; };
struct qcom_q6v5 { struct rproc *rproc; unsigned spawn_bit, stop_bit; bool running; };
struct qcom_rproc_ssr { int unused; }; struct qcom_rproc_glink { int unused; };
struct clk_bulk_data { int unused; };
struct wcss_data { u32 pasid; bool share_upd_info_to_q6; u8 bootargs_version; };
struct userpd;

static bool fw_alive;
static int msa[4], bad_unlock, double_lock, spawns[4], root_starts, reports[4];
static int fail_spawn, fail_load;
static struct rproc root, uproc[2];
static int idx(struct rproc *r) { return r == &root ? 0 : (int)(r - uproc) + 1; }
static void rproc_report_crash(struct rproc *r, int type) { reports[idx(r)]++; r->crash_handler.pending = 1; }
static int qcom_q6v5_prepare(struct qcom_q6v5 *q) { return 0; }
static int qcom_scm_pas_auth_and_reset(u32 p) { fw_alive = true; root_starts++; return 0; }
static int qcom_q6v5_wait_for_start(struct qcom_q6v5 *q, int t) { return fw_alive ? 0 : -ETIMEDOUT; }
static int qcom_q6v5_request_spawn(struct qcom_q6v5 *q) {
    if (!fw_alive || fail_spawn) { fail_spawn = 0; return -ETIMEDOUT; }
    spawns[idx(q->rproc)]++; return 0; }
static int qcom_q6v5_request_stop(struct qcom_q6v5 *q, void *s) { return 0; }
static int qcom_scm_msa_lock(u32 p) { if (msa[p >> 8]++) double_lock++; return 0; }
static int qcom_scm_msa_unlock(u32 p) { if (!msa[p >> 8]) { bad_unlock++; return -EINVAL; } msa[p >> 8]--; return 0; }
static int qcom_scm_internal_wifi_powerup(u32 p) { return 0; }
static int qcom_scm_internal_wifi_shutdown(u32 p) { return 0; }
#define qcom_mdt_load_pd_seg(...) (fail_load ? (fail_load = 0, -EINVAL) : 0)
static int rproc_boot(struct rproc *r);
static int rproc_shutdown(struct rproc *r);
"""

MODEL = r"""
/* remoteproc core model: rproc_start() = .load then .start, no .stop on failure */
static int model_start(struct rproc *r) {
    struct firmware fw;
    int ret;
    if (r == &root) return q6_wcss_start(r);
    ret = wcss_pd_load(r, &fw);
    return ret ? ret : wcss_pd_start(r);
}
static int model_stop(struct rproc *r) {
    if (r == &root) { fw_alive = false; return 0; }   /* q6_wcss_stop: unchanged */
    return wcss_pd_stop(r);
}
static int rproc_boot(struct rproc *r) {
    int ret;
    if (++r->power > 1) return 0;                     /* also while CRASHED */
    ret = model_start(r);
    if (ret) { r->power--; return ret; }
    r->state = RPROC_RUNNING; return 0;
}
static int rproc_shutdown(struct rproc *r) {
    int ret;
    if (r->state != RPROC_RUNNING && r->state != RPROC_CRASHED) return -EINVAL;
    if (--r->power) return 0;
    ret = model_stop(r);
    if (ret) { r->power++; return ret; }
    r->state = RPROC_OFFLINE; return 0;
}
static void crash_work(struct work_struct *w) {        /* rproc_crash_handler_work */
    struct rproc *r = container_of(w, struct rproc, crash_handler);
    if (!r->mid_recovery) {
        if (r->state == RPROC_CRASHED || r->state == RPROC_OFFLINE) return;
        r->state = RPROC_CRASHED;
    }
    r->mid_recovery = 0;
    if (r->recovery_disabled) return;
    if (model_stop(r)) return;                         /* rproc_boot_recovery */
    r->state = RPROC_OFFLINE;
    if (!model_start(r)) r->state = RPROC_RUNNING;
}

static struct q6_wcss wcss; static struct userpd ud[2];
static struct device root_dev, udev[2]; static struct wcss_data desc = { 0xd, true, 1 };
static void setup(void) {
    memset(&wcss, 0, sizeof(wcss)); memset(ud, 0, sizeof(ud));
    memset(&root, 0, sizeof(root)); memset(uproc, 0, sizeof(uproc));
    memset(msa, 0, sizeof(msa)); memset(spawns, 0, sizeof(spawns)); memset(reports, 0, sizeof(reports));
    bad_unlock = double_lock = root_starts = fail_spawn = fail_load = 0; fw_alive = false;
    root.priv = &wcss; root.crash_handler.fn = crash_work; root_dev.drvdata = &root;
    wcss.desc = &desc;
#ifdef HAVE_RECOVERY
    INIT_WORK(&wcss.upd_recovery, q6_wcss_recover_userpds);
#endif
    for (int i = 0; i < 2; i++) {
        ud[i].pd_asid = i + 1; ud[i].dev = &udev[i]; udev[i].parent = &root_dev;
        ud[i].q6.rproc = &uproc[i]; ud[i].q6.spawn_bit = 8 * (i + 1); ud[i].q6.stop_bit = 1;
        uproc[i].priv = &ud[i]; uproc[i].crash_handler.fn = crash_work;
        wcss.upd[i + 1] = &ud[i];
    }
}
static void drain(void) {
    for (int n = 0; n < 32; n++) {
        flush_work(&root.crash_handler);
        flush_work(&uproc[0].crash_handler); flush_work(&uproc[1].crash_handler);
#ifdef HAVE_RECOVERY
        flush_work(&wcss.upd_recovery);
#endif
    }
}
static void boot_both(void) { rproc_boot(&uproc[0]); rproc_boot(&uproc[1]); drain(); memset(reports, 0, sizeof(reports)); }
static bool both_up(void) {
    return uproc[0].state == RPROC_RUNNING && uproc[1].state == RPROC_RUNNING &&
           root.state == RPROC_RUNNING && root.power == 2 && msa[1] == 1 && msa[2] == 1 &&
           !bad_unlock && !double_lock;
}
static int fails;
static void check(const char *name, bool ok) { printf("%s %s\n", ok ? "PASS" : "FAIL", name); fails += !ok; }

int main(void) {
    setup(); boot_both();
    check("S1 both user PDs boot once, root PD held twice, no crash reported", both_up() && root_starts == 1);
    rproc_shutdown(&uproc[0]); rproc_shutdown(&uproc[1]);
    check("S1 shutdown releases MSA locks and the root PD", root.power == 0 && root.state == RPROC_OFFLINE && !msa[1] && !msa[2] && !bad_unlock);

    setup(); fail_spawn = 1;
    check("S2 spawn timeout on boot fails cleanly", rproc_boot(&uproc[0]) != 0);
    check("S2 failed start releases the MSA lock and the root PD", !msa[1] && root.power == 0 && root.state == RPROC_OFFLINE);

    setup(); fail_load = 1;
    check("S3 failed segment load releases the root PD", rproc_boot(&uproc[0]) != 0 && root.power == 0 && !msa[1]);

    setup(); boot_both(); fw_alive = false;
    root.state = RPROC_CRASHED; root.mid_recovery = 1; root.crash_handler.pending = 1;
    uproc[0].crash_handler.pending = 1;                /* user PD recovery runs first */
    flush_work(&uproc[0].crash_handler); drain();
    check("S4 user PD recovery waits for the crashed root PD and both radios return", both_up());

    setup(); boot_both(); fw_alive = false; root.crash_handler.pending = 1;
    drain();
    check("S5 root-only crash: both user PDs respawned after the root PD restart",
          both_up() && reports[1] == 1 && reports[2] == 1 && root_starts == 2);

    setup(); boot_both(); fw_alive = false;
    root.crash_handler.pending = 1; uproc[0].crash_handler.pending = 1;
    flush_work(&root.crash_handler); flush_work(&uproc[0].crash_handler); drain();
    check("S6 a user PD that already respawned is not restarted again",
          both_up() && reports[1] == 0 && spawns[1] == 2 && spawns[2] == 2);

    setup(); boot_both(); uproc[1].crash_handler.pending = 1;
    drain();
    check("S7 user-PD-only crash keeps the root PD and the other radio running",
          both_up() && root_starts == 1 && spawns[1] == 1 && spawns[2] == 2 && !reports[1] && !reports[2]);

    setup(); boot_both(); uproc[0].recovery_disabled = true; fw_alive = false;
    root.crash_handler.pending = 1; drain();
    check("S8 recovery_disabled is honoured; the other radio still returns",
          uproc[0].state == RPROC_CRASHED && uproc[1].state == RPROC_RUNNING);
    return fails ? 1 : 0;
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--expect-fail", action="store_true")
    a = ap.parse_args()
    src = Path(a.source).read_text()
    parts = [HEADER, struct(src, "q6_wcss"), struct(src, "userpd")]
    have = {n: function(src, n) for n in REQUIRED + OPTIONAL}
    missing = [n for n in REQUIRED if not have[n]]
    if missing:
        raise SystemExit(f"missing driver definitions: {missing}")
    if have["q6_wcss_recover_userpds"]:
        parts.insert(0, "#define HAVE_RECOVERY 1\n")
    parts.append("static void q6_wcss_recover_userpds(struct work_struct *w);\n")
    for n in OPTIONAL[:1] + REQUIRED + OPTIONAL[1:]:
        if have[n]:
            parts.append(have[n])
    if not have["q6_wcss_recover_userpds"]:
        parts.append("static void q6_wcss_recover_userpds(struct work_struct *w) {}\n")
    parts.append(MODEL)
    with tempfile.TemporaryDirectory() as d:
        c, exe = Path(d, "mpd.c"), Path(d, "mpd")
        c.write_text("\n".join(parts))
        subprocess.run(["cc", "-std=gnu11", "-w", "-Werror=implicit-function-declaration",
                        "-o", str(exe), str(c)], check=True)
        rc = subprocess.run([str(exe)]).returncode
    if a.expect_fail:
        print("PASS scenarios detect the unpatched driver" if rc else "FAIL unpatched driver passed every scenario")
        return 0 if rc else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
