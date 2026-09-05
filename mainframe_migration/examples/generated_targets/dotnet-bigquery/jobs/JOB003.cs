/* JOB003 — behavior-preserving migrated job.
 * Source: jcl/JOB003.jcl
 * Purpose: run every source step in order; preserve unusual rules.
 * Inputs and outputs: declared DD bindings in the sealed process model.
 * SQL operations use the selected database adapter; no source repair is applied.
 */
using System;
using System.Collections.Generic;

public static class JOB003 {
    // Run CALCFEE from CALCFEE.cbl; do not simplify its conditions.
    static void program_CALCFEE(MfRuntime.Context ctx, Dictionary<string,object> dd, MfRuntime.Ref[] arguments) {
        var s = new MfRuntime.Fields(ctx.layout("CALCFEE"));
        var streams = new Dictionary<string,MfRuntime.RecordFile>();
        if (arguments.Length != 3) throw new Exception("CALL argument count differs from source linkage.");
        s.bind("L-AMOUNT", arguments[0]);
        s.bind("L-TYPE", arguments[1]);
        s.bind("L-FEE", arguments[2]);
        // CALCFEE.cbl:9: Retain both source outcomes, including unusual exceptions.
        ctx.hit("CALCFEE:CALCFEE.cbl:9:1");
        if (MfRuntime.truth(ctx.relation(s.get("L-TYPE"), "=", "X"))) {
            // CALCFEE.cbl:11: Copy the source value using the receiving field width.
            ctx.hit("CALCFEE:CALCFEE.cbl:11:2");
            var value_2 = Dec.Parse("7");
            s.set("L-FEE", value_2);
        } else {
            // CALCFEE.cbl:14: Apply the source calculation and its receiving field truncation.
            ctx.hit("CALCFEE:CALCFEE.cbl:14:3");
            s.set("L-FEE", MfRuntime.math("/", s.get("L-AMOUNT"), Dec.Parse("100")));
        }
        // CALCFEE.cbl:16: End this source program at the original return statement.
        ctx.hit("CALCFEE:CALCFEE.cbl:16:4");
        return;
    }
    // Run FEEPOST from FEEPOST.cbl; do not simplify its conditions.
    static void program_FEEPOST(MfRuntime.Context ctx, Dictionary<string,object> dd, MfRuntime.Ref[] arguments) {
        var s = new MfRuntime.Fields(ctx.layout("FEEPOST"));
        var streams = new Dictionary<string,MfRuntime.RecordFile>();
        if (arguments.Length != 0) throw new Exception("CALL argument count differs from source linkage.");
        // FEEPOST.cbl:19: Open the files selected by this source step.
        ctx.hit("FEEPOST:FEEPOST.cbl:19:1");
        streams["INFILE"] = ctx.open(MfRuntime.obj(dd["SORTED"]), "INPUT", s.length("IN-RECORD"));
        streams["OUTFILE"] = ctx.open(MfRuntime.obj(dd["FEES"]), "OUTPUT", s.length("OUT-RECORD"));
        // FEEPOST.cbl:20: Repeat until the original stopping condition is true.
        ctx.hit("FEEPOST:FEEPOST.cbl:20:2");
        while (!MfRuntime.truth(ctx.relation(s.get("FINISHED"), "=", "Y"))) {
            // FEEPOST.cbl:21: Read one complete record and keep the source end-of-file behavior.
            ctx.hit("FEEPOST:FEEPOST.cbl:21:3");
            var record_3 = streams["INFILE"].read();
            if (record_3 == null) {
                // FEEPOST.cbl:22: Copy the source value using the receiving field width.
                ctx.hit("FEEPOST:FEEPOST.cbl:22:4");
                var value_4 = "Y";
                s.set("FINISHED", value_4);
            } else {
                s.set("IN-RECORD", record_3);
                // FEEPOST.cbl:24: Copy the source value using the receiving field width.
                ctx.hit("FEEPOST:FEEPOST.cbl:24:5");
                var value_5 = s.get("IN-RECORD");
                s.set("C-RECORD", value_5);
                // FEEPOST.cbl:25: Copy the source value using the receiving field width.
                ctx.hit("FEEPOST:FEEPOST.cbl:25:6");
                var value_6 = s.get("C-RECORD");
                s.set("F-RECORD", value_6);
                // FEEPOST.cbl:26: Share caller storage with the called source program.
                ctx.hit("FEEPOST:FEEPOST.cbl:26:7");
                program_CALCFEE(ctx, dd, new MfRuntime.Ref[] {s.reference("C-AMOUNT"), s.reference("C-TYPE"), s.reference("F-FEE")});
                // FEEPOST.cbl:27: Write the complete record without trimming or deduplicating it.
                ctx.hit("FEEPOST:FEEPOST.cbl:27:8");
                s.set("OUT-RECORD", s.get("F-RECORD"));
                streams["OUTFILE"].write(s.raw("OUT-RECORD"));
            }
        }
        // FEEPOST.cbl:30: Close exactly the files named by the source.
        ctx.hit("FEEPOST:FEEPOST.cbl:30:9");
        streams["INFILE"].close();
        streams["OUTFILE"].close();
        // FEEPOST.cbl:31: End this source program at the original return statement.
        ctx.hit("FEEPOST:FEEPOST.cbl:31:10");
        return;
    }
    // Execute S010 (FEEPOST) using the source DD bindings.
    static void step_S010(MfRuntime.Context ctx) {
        var dd = ctx.dd("JOB003", "S010");
        program_FEEPOST(ctx, dd, new MfRuntime.Ref[0]);
        ctx.end_step();
    }
    // Run all source steps exactly once. A failure stops rather than skips work.
    public static void run(MfRuntime.Context ctx) {
        step_S010(ctx);
        ctx.finish();
    }
}
