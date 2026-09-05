/* JOB001 — behavior-preserving migrated job.
 * Source: jcl/JOB001.jcl
 * Purpose: run every source step in order; preserve unusual rules.
 * Inputs and outputs: declared DD bindings in the sealed process model.
 * SQL operations use the selected database adapter; no source repair is applied.
 */
import java.util.*;
import java.math.BigDecimal;

public final class JOB001 {
    // Run CLASSIFY from CLASSIFY.cbl; do not simplify its conditions.
    static void program_CLASSIFY(MfRuntime.Context ctx, Map<String,Object> dd, MfRuntime.Ref[] arguments) throws Exception {
        var s = new MfRuntime.Fields(ctx.layout("CLASSIFY"));
        var streams = new HashMap<String,MfRuntime.RecordFile>();
        if (arguments.length != 0) throw new IllegalArgumentException("CALL argument count differs from source linkage.");
        // CLASSIFY.cbl:25: Open the files selected by this source step.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:25:1");
        streams.put("INFILE", ctx.open(MfRuntime.obj(dd.get("RAWIN")), "INPUT", s.length("IN-RECORD")));
        streams.put("DATEFILE", ctx.open(MfRuntime.obj(dd.get("BDATE")), "INPUT", s.length("DATE-RECORD")));
        streams.put("GOODFILE", ctx.open(MfRuntime.obj(dd.get("ACCEPT")), "OUTPUT", s.length("GOOD-RECORD")));
        streams.put("BADFILE", ctx.open(MfRuntime.obj(dd.get("REJECT")), "OUTPUT", s.length("BAD-RECORD")));
        // CLASSIFY.cbl:26: Read one complete record and keep the source end-of-file behavior.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:26:2");
        var record_2 = streams.get("DATEFILE").read();
        if (record_2 == null) {
            // CLASSIFY.cbl:27: End this source program at the original return statement.
            ctx.hit("CLASSIFY:CLASSIFY.cbl:27:3");
            return;
        } else {
            s.set("DATE-RECORD", record_2);
            // CLASSIFY.cbl:28: Copy the source value using the receiving field width.
            ctx.hit("CLASSIFY:CLASSIFY.cbl:28:4");
            var value_4 = s.get("DATE-RECORD");
            s.set("RUN-DATE", value_4);
        }
        // CLASSIFY.cbl:30: Close exactly the files named by the source.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:30:5");
        streams.get("DATEFILE").close();
        // CLASSIFY.cbl:31: Repeat until the original stopping condition is true.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:31:6");
        while (!MfRuntime.truth(ctx.relation(s.get("FINISHED"), "=", "Y"))) {
            // CLASSIFY.cbl:32: Read one complete record and keep the source end-of-file behavior.
            ctx.hit("CLASSIFY:CLASSIFY.cbl:32:7");
            var record_7 = streams.get("INFILE").read();
            if (record_7 == null) {
                // CLASSIFY.cbl:33: Copy the source value using the receiving field width.
                ctx.hit("CLASSIFY:CLASSIFY.cbl:33:8");
                var value_8 = "Y";
                s.set("FINISHED", value_8);
            } else {
                s.set("IN-RECORD", record_7);
                // CLASSIFY.cbl:35: Copy the source value using the receiving field width.
                ctx.hit("CLASSIFY:CLASSIFY.cbl:35:9");
                var value_9 = s.get("IN-RECORD");
                s.set("C-RECORD", value_9);
                // CLASSIFY.cbl:38: Retain both source outcomes, including unusual exceptions.
                ctx.hit("CLASSIFY:CLASSIFY.cbl:38:10");
                if (MfRuntime.truth(ctx.relation(s.get("C-TYPE"), "=", "X"))) {
                    // CLASSIFY.cbl:39: Write the complete record without trimming or deduplicating it.
                    ctx.hit("CLASSIFY:CLASSIFY.cbl:39:11");
                    s.set("GOOD-RECORD", s.get("C-RECORD"));
                    streams.get("GOODFILE").write(s.raw("GOOD-RECORD"));
                } else {
                    // CLASSIFY.cbl:41: Retain both source outcomes, including unusual exceptions.
                    ctx.hit("CLASSIFY:CLASSIFY.cbl:41:12");
                    if (MfRuntime.truth(ctx.relation(s.get("C-AMOUNT"), ">=", new BigDecimal("100000")))) {
                        // CLASSIFY.cbl:42: Retain both source outcomes, including unusual exceptions.
                        ctx.hit("CLASSIFY:CLASSIFY.cbl:42:13");
                        if (MfRuntime.truth(ctx.relation(s.get("C-DATE"), "<=", s.get("RUN-DATE")))) {
                            // CLASSIFY.cbl:43: Write the complete record without trimming or deduplicating it.
                            ctx.hit("CLASSIFY:CLASSIFY.cbl:43:14");
                            s.set("GOOD-RECORD", s.get("C-RECORD"));
                            streams.get("GOODFILE").write(s.raw("GOOD-RECORD"));
                        } else {
                            // CLASSIFY.cbl:45: Write the complete record without trimming or deduplicating it.
                            ctx.hit("CLASSIFY:CLASSIFY.cbl:45:15");
                            s.set("BAD-RECORD", s.get("C-RECORD"));
                            streams.get("BADFILE").write(s.raw("BAD-RECORD"));
                        }
                    } else {
                        // CLASSIFY.cbl:48: Write the complete record without trimming or deduplicating it.
                        ctx.hit("CLASSIFY:CLASSIFY.cbl:48:16");
                        s.set("BAD-RECORD", s.get("C-RECORD"));
                        streams.get("BADFILE").write(s.raw("BAD-RECORD"));
                    }
                }
            }
        }
        // CLASSIFY.cbl:53: Close exactly the files named by the source.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:53:17");
        streams.get("INFILE").close();
        streams.get("GOODFILE").close();
        streams.get("BADFILE").close();
        // CLASSIFY.cbl:54: End this source program at the original return statement.
        ctx.hit("CLASSIFY:CLASSIFY.cbl:54:18");
        return;
    }
    // Execute S010 (CLASSIFY) using the source DD bindings.
    static void step_S010(MfRuntime.Context ctx) throws Exception {
        var dd = ctx.dd("JOB001", "S010");
        program_CLASSIFY(ctx, dd, new MfRuntime.Ref[0]);
        ctx.end_step();
    }
    // Run all source steps exactly once. A failure stops rather than skips work.
    public static void run(MfRuntime.Context ctx) throws Exception {
        step_S010(ctx);
        ctx.finish();
    }
}
