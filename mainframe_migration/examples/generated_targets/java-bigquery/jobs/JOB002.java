/* JOB002 — behavior-preserving migrated job.
 * Source: jcl/JOB002.jcl
 * Purpose: run every source step in order; preserve unusual rules.
 * Inputs and outputs: declared DD bindings in the sealed process model.
 * SQL operations use the selected database adapter; no source repair is applied.
 */
import java.util.*;
import java.math.BigDecimal;

public final class JOB002 {
    // Execute S010 (SORT) using the source DD bindings.
    static void step_S010(MfRuntime.Context ctx) throws Exception {
        var dd = ctx.dd("JOB002", "S010");
        ctx.sort(MfRuntime.obj(dd.get("SORTIN")), MfRuntime.obj(dd.get("SORTOUT")), new int[][] {new int[] {1,6,0,0}});
        ctx.end_step();
    }
    // Run all source steps exactly once. A failure stops rather than skips work.
    public static void run(MfRuntime.Context ctx) throws Exception {
        step_S010(ctx);
        ctx.finish();
    }
}
