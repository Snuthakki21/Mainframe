/* Start one native generated job and record its actual outcome. */
import java.nio.file.*;
import java.util.*;

public final class Main {
    public static void main(String[] args)throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("Use Main JOB context.json result.json");
        Map<String,Object> payload=MfRuntime.obj(Json.parse(Files.readString(Path.of(args[1]))));
        Map<String,Object> result=new LinkedHashMap<>();result.put("status","FAILED");result.put("return_code",0);
        MfRuntime.Context ctx=null;
        try{ctx=new MfRuntime.Context(payload);
            switch(args[0]) {
                case "JOB001": JOB001.run(ctx); break;
                case "JOB002": JOB002.run(ctx); break;
                case "JOB003": JOB003.run(ctx); break;
                case "JOB004": JOB004.run(ctx); break;
                case "JOB005": JOB005.run(ctx); break;
                default:throw new IllegalArgumentException("Unknown generated job");
            }
            result.put("status","PASSED");
        }catch(Exception e){result.put("error",e.getClass().getSimpleName()+": "+e.getMessage());}
        finally{if(ctx!=null){result.put("events",ctx.events);result.put("operations",ctx.db.operations);try{ctx.close();}catch(Exception e){result.put("status","FAILED");result.put("error","Cleanup failed: "+e.getMessage());}}Files.writeString(Path.of(args[2]),Json.dump(result)+"\n");}
        if(!result.get("status").equals("PASSED"))System.exit(1);
    }
}
