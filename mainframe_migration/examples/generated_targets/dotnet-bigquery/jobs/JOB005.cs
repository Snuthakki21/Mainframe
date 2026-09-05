/* JOB005 — behavior-preserving migrated job.
 * Source: jcl/JOB005.jcl
 * Purpose: run every source step in order; preserve unusual rules.
 * Inputs and outputs: declared DD bindings in the sealed process model.
 * SQL operations use the selected database adapter; no source repair is applied.
 */
using System;
using System.Collections.Generic;

public static class JOB005 {
    // Run TOTALS from TOTALS.cbl; do not simplify its conditions.
    static void program_TOTALS(MfRuntime.Context ctx, Dictionary<string,object> dd, MfRuntime.Ref[] arguments) {
        var s = new MfRuntime.Fields(ctx.layout("TOTALS"));
        var streams = new Dictionary<string,MfRuntime.RecordFile>();
        if (arguments.Length != 0) throw new Exception("CALL argument count differs from source linkage.");
        // TOTALS.cbl:22: Open the files selected by this source step.
        ctx.hit("TOTALS:TOTALS.cbl:22:1");
        streams["INFILE"] = ctx.open(MfRuntime.obj(dd["FEES"]), "INPUT", s.length("IN-RECORD"));
        streams["OUTFILE"] = ctx.open(MfRuntime.obj(dd["TOTAL"]), "OUTPUT", s.length("OUT-RECORD"));
        // TOTALS.cbl:23: Repeat until the original stopping condition is true.
        ctx.hit("TOTALS:TOTALS.cbl:23:2");
        while (!MfRuntime.truth(ctx.relation(s.get("FINISHED"), "=", "Y"))) {
            // TOTALS.cbl:24: Read one complete record and keep the source end-of-file behavior.
            ctx.hit("TOTALS:TOTALS.cbl:24:3");
            var record_3 = streams["INFILE"].read();
            if (record_3 == null) {
                // TOTALS.cbl:25: Copy the source value using the receiving field width.
                ctx.hit("TOTALS:TOTALS.cbl:25:4");
                var value_4 = "Y";
                s.set("FINISHED", value_4);
            } else {
                s.set("IN-RECORD", record_3);
                // TOTALS.cbl:27: Copy the source value using the receiving field width.
                ctx.hit("TOTALS:TOTALS.cbl:27:5");
                var value_5 = s.get("IN-RECORD");
                s.set("F-RECORD", value_5);
                // TOTALS.cbl:28: Add the source value without introducing a new rounding rule.
                ctx.hit("TOTALS:TOTALS.cbl:28:6");
                var value_6 = Dec.Parse("1");
                s.set("ITEM-COUNT", MfRuntime.math("+", s.get("ITEM-COUNT"), value_6));
                // TOTALS.cbl:29: Add the source value without introducing a new rounding rule.
                ctx.hit("TOTALS:TOTALS.cbl:29:7");
                var value_7 = s.get("F-AMOUNT");
                s.set("TOTAL-AMOUNT", MfRuntime.math("+", s.get("TOTAL-AMOUNT"), value_7));
                // TOTALS.cbl:30: Add the source value without introducing a new rounding rule.
                ctx.hit("TOTALS:TOTALS.cbl:30:8");
                var value_8 = s.get("F-FEE");
                s.set("TOTAL-FEE", MfRuntime.math("+", s.get("TOTAL-FEE"), value_8));
            }
        }
        // TOTALS.cbl:33: Write the complete record without trimming or deduplicating it.
        ctx.hit("TOTALS:TOTALS.cbl:33:9");
        s.set("OUT-RECORD", s.get("TOTAL-RECORD"));
        streams["OUTFILE"].write(s.raw("OUT-RECORD"));
        // TOTALS.cbl:34: Close exactly the files named by the source.
        ctx.hit("TOTALS:TOTALS.cbl:34:10");
        streams["INFILE"].close();
        streams["OUTFILE"].close();
        // TOTALS.cbl:35: End this source program at the original return statement.
        ctx.hit("TOTALS:TOTALS.cbl:35:11");
        return;
    }
    // Execute S010 (TOTALS) using the source DD bindings.
    static void step_S010(MfRuntime.Context ctx) {
        var dd = ctx.dd("JOB005", "S010");
        program_TOTALS(ctx, dd, new MfRuntime.Ref[0]);
        ctx.end_step();
    }
    // Run all source steps exactly once. A failure stops rather than skips work.
    public static void run(MfRuntime.Context ctx) {
        step_S010(ctx);
        ctx.finish();
    }
}
