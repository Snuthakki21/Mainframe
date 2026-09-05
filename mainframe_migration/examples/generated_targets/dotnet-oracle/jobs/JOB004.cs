/* JOB004 — behavior-preserving migrated job.
 * Source: jcl/JOB004.jcl
 * Purpose: run every source step in order; preserve unusual rules.
 * Inputs and outputs: declared DD bindings in the sealed process model.
 * SQL operations use the selected database adapter; no source repair is applied.
 */
using System;
using System.Collections.Generic;

public static class JOB004 {
    // Run LOADDB from LOADDB.cbl; do not simplify its conditions.
    static void program_LOADDB(MfRuntime.Context ctx, Dictionary<string,object> dd, MfRuntime.Ref[] arguments) {
        var s = new MfRuntime.Fields(ctx.layout("LOADDB"));
        var streams = new Dictionary<string,MfRuntime.RecordFile>();
        if (arguments.Length != 0) throw new Exception("CALL argument count differs from source linkage.");
        // LOADDB.cbl:16: Open the files selected by this source step.
        ctx.hit("LOADDB:LOADDB.cbl:16:1");
        streams["INFILE"] = ctx.open(MfRuntime.obj(dd["FEES"]), "INPUT", s.length("IN-RECORD"));
        // LOADDB.cbl:17: Repeat until the original stopping condition is true.
        ctx.hit("LOADDB:LOADDB.cbl:17:2");
        while (!MfRuntime.truth(ctx.relation(s.get("FINISHED"), "=", "Y"))) {
            // LOADDB.cbl:18: Read one complete record and keep the source end-of-file behavior.
            ctx.hit("LOADDB:LOADDB.cbl:18:3");
            var record_3 = streams["INFILE"].read();
            if (record_3 == null) {
                // LOADDB.cbl:19: Copy the source value using the receiving field width.
                ctx.hit("LOADDB:LOADDB.cbl:19:4");
                var value_4 = "Y";
                s.set("FINISHED", value_4);
            } else {
                s.set("IN-RECORD", record_3);
                // LOADDB.cbl:21: Copy the source value using the receiving field width.
                ctx.hit("LOADDB:LOADDB.cbl:21:5");
                var value_5 = s.get("IN-RECORD");
                s.set("F-RECORD", value_5);
                // LOADDB.cbl:22: Add the source value without introducing a new rounding rule.
                ctx.hit("LOADDB:LOADDB.cbl:22:6");
                var value_6 = Dec.Parse("1");
                s.set("ROW-NUMBER", MfRuntime.math("+", s.get("ROW-NUMBER"), value_6));
                // LOADDB.cbl:23: Insert the source columns through the selected database adapter.
                ctx.hit("LOADDB:LOADDB.cbl:23:7");
                ctx.insert("ACCOUNT_LEDGER", new string[] {"SEQ", "ACCOUNT_ID", "AMOUNT_CENTS", "BUSINESS_DATE", "CATEGORY", "FEE_CENTS"}, new object[] {s.get("ROW-NUMBER"), s.get("F-ACCOUNT"), s.get("F-AMOUNT"), s.get("F-DATE"), s.get("F-TYPE"), s.get("F-FEE")});
            }
        }
        // LOADDB.cbl:31: Close exactly the files named by the source.
        ctx.hit("LOADDB:LOADDB.cbl:31:8");
        streams["INFILE"].close();
        // LOADDB.cbl:32: Commit only because the source explicitly requests it.
        ctx.hit("LOADDB:LOADDB.cbl:32:9");
        ctx.commit();
        // LOADDB.cbl:33: End this source program at the original return statement.
        ctx.hit("LOADDB:LOADDB.cbl:33:10");
        return;
    }
    // Execute S010 (IEBGENER) using the source DD bindings.
    static void step_S010(MfRuntime.Context ctx) {
        var dd = ctx.dd("JOB004", "S010");
        ctx.copy(MfRuntime.obj(dd["SYSUT1"]), MfRuntime.obj(dd["SYSUT2"]));
        ctx.end_step();
    }
    // Execute S020 (LOADDB) using the source DD bindings.
    static void step_S020(MfRuntime.Context ctx) {
        var dd = ctx.dd("JOB004", "S020");
        program_LOADDB(ctx, dd, new MfRuntime.Ref[0]);
        ctx.end_step();
    }
    // Run all source steps exactly once. A failure stops rather than skips work.
    public static void run(MfRuntime.Context ctx) {
        step_S010(ctx);
        step_S020(ctx);
        ctx.finish();
    }
}
