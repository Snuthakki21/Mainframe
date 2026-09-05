/* Database-specific work is separate from generated business functions.
 * JDBC is used for SQLite/Oracle; BigQuery uses documented REST session jobs.
 * Contract recordings exercise bindings and transaction calls, not a live DB.
 */
import java.util.*;
import java.math.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.net.*;
import java.net.http.*;
import java.time.Duration;

public final class MfDatabase implements AutoCloseable {
    public static final String TARGET="@@DATABASE@@";
    final Map<String,Object> payload,schema;final boolean contract;
    public final List<Object> operations=new ArrayList<>();
    Connection conn;boolean pending=false,uncertain=false;String session=null;
    public MfDatabase(Map<String,Object> p){payload=p;schema=MfRuntime.obj(p.get("schema"));contract="contract".equals(p.get("execution_mode"));
        if(!TARGET.equals(p.get("database")))throw new IllegalArgumentException("Context database differs from generated target");
        if(!contract&&!MfRuntime.list(p.get("capability_blockers")).isEmpty())throw new IllegalArgumentException("Unresolved target capability blockers");
        if(!contract&&!TARGET.equals("sqlite")&&!Boolean.TRUE.equals(p.get("allow_remote")))throw new IllegalArgumentException("Remote execution is not enabled");}
    // Values of configuration entries name environment variables, never inline passwords.
    String env(String key){String name=(String)MfRuntime.obj(MfRuntime.obj(payload.get("connections")).get(TARGET)).get(key);String value=System.getenv(name);if(value==null||value.isEmpty())throw new IllegalArgumentException("Required environment variable missing: "+name);return value;}
    String identifier(String name){if(!name.matches("[A-Z][A-Z0-9_]{0,127}"))throw new IllegalArgumentException("Unsafe SQL identifier");return TARGET.equals("bigquery")?"`"+name+"`":"\""+name+"\"";}
    Object exact(Map<String,Object> c,Object value){if(value==null){if(!Boolean.TRUE.equals(c.get("nullable")))throw new IllegalArgumentException("NULL violates source schema");return null;}
        String kind=(String)c.get("kind");if(kind.equals("text")){if(!(value instanceof String))throw new IllegalArgumentException("Text type differs from source");String s=(String)value;int length=MfRuntime.integer(c.get("length"));if(s.length()>length)throw new IllegalArgumentException("Text exceeds source width");if(TARGET.equals("oracle")&&s.isEmpty())throw new IllegalArgumentException("Oracle empty-string mapping is unresolved");return c.get("source_type").equals("CHAR")?MfRuntime.pad(s,length):s;}
        BigDecimal n=MfRuntime.num(value);if(kind.equals("integer")){if(n.stripTrailingZeros().scale()>0||n.compareTo(new BigDecimal((String)c.get("minimum")))<0||n.compareTo(new BigDecimal((String)c.get("maximum")))>0)throw new IllegalArgumentException("Integer violates source bounds");return n.longValueExact();}
        int scale=MfRuntime.integer(c.get("scale")),precision=MfRuntime.integer(c.get("precision"));if(n.abs().compareTo(BigDecimal.TEN.pow(precision-scale))>=0)throw new IllegalArgumentException("Decimal exceeds source precision");return n.setScale(scale,RoundingMode.UNNECESSARY).toPlainString();}
    // Open only the selected driver. Missing drivers cause failure, not a fallback database.
    void connect()throws Exception{if(conn!=null)return;if(TARGET.equals("sqlite")){Class.forName("org.sqlite.JDBC");conn=DriverManager.getConnection("jdbc:sqlite:"+Path.of((String)payload.get("work_root"),"local.sqlite"));try(Statement s=conn.createStatement()){s.execute("PRAGMA foreign_keys=ON");}}
        else if(TARGET.equals("oracle")){Class.forName("oracle.jdbc.OracleDriver");String dsn=env("dsn_env");String url=dsn.startsWith("jdbc:")?dsn:"jdbc:oracle:thin:@//"+(dsn.startsWith("//")?dsn.substring(2):dsn);conn=DriverManager.getConnection(url,env("user_env"),env("password_env"));}if(conn!=null)conn.setAutoCommit(false);}
    // Send one REST request; no mutation retry hides a potentially committed operation.
    Map<String,Object> wire(String method,String url,Object body)throws Exception{var builder=HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(30)).header("Authorization","Bearer "+env("token_env")).header("Content-Type","application/json");
        builder.method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(Json.dump(body)));
        var response=HttpClient.newHttpClient().send(builder.build(),HttpResponse.BodyHandlers.ofString());if(response.statusCode()<200||response.statusCode()>=300)throw new IOExceptionLike("BigQuery HTTP "+response.statusCode()+"; inspect recorded job ID");return MfRuntime.obj(Json.parse(response.body()));}
    static final class IOExceptionLike extends Exception {IOExceptionLike(String s){super(s);}}
    @SuppressWarnings("unchecked") static Map<String,Object> child(Map<String,Object> m,String key){Object x=m.get(key);return x instanceof Map?(Map<String,Object>)x:new LinkedHashMap<>();}
    // Keep session state and remote job IDs. Timeout is UNKNOWN, never a successful rollback.
    Map<String,Object> query(String sql,List<Object> params,boolean create)throws Exception{
        String project=env("project_env"),dataset=env("dataset_env"),location=env("location_env");if(!project.matches("[A-Za-z0-9_-]+")||!dataset.matches("[A-Za-z0-9_]+")||!location.matches("[A-Za-z0-9_-]+"))throw new IllegalArgumentException("Invalid BigQuery identifiers");
        String id="migration_"+UUID.randomUUID().toString().replace("-","");String base="https://bigquery.googleapis.com/bigquery/v2/projects/"+project+"/jobs";
        Map<String,Object> q=new LinkedHashMap<>();q.put("query",sql);q.put("useLegacySql",false);q.put("defaultDataset",Map.of("projectId",project,"datasetId",dataset));if(!params.isEmpty()){q.put("parameterMode","NAMED");q.put("queryParameters",params);}if(create)q.put("createSession",true);else if(session!=null)q.put("connectionProperties",List.of(Map.of("key","session_id","value",session)));
        Map<String,Object> body=Map.of("jobReference",Map.of("projectId",project,"jobId",id,"location",location),"configuration",Map.of("query",q,"jobTimeoutMs","60000"));
        Map<String,Object> record=new LinkedHashMap<>();record.put("job_id",id);record.put("session_id",session);record.put("operation",sql.split(" ")[0]);Files.writeString(Path.of((String)payload.get("work_root"),"remote_job_ids.jsonl"),Json.dump(record)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        Map<String,Object> result;
        try{result=wire("POST",base,body);long deadline=System.nanoTime()+60_000_000_000L;if(create){Object s=child(child(result,"statistics"),"sessionInfo").get("sessionId");if(s!=null)session=s.toString();}
            while(!"DONE".equals(child(result,"status").get("state"))){if(System.nanoTime()>deadline)throw new IOExceptionLike("Remote outcome unknown; no retry is made");Thread.sleep(250);result=wire("GET",base+"/"+id+"?location="+location,null);}if(create){Object s=child(child(result,"statistics"),"sessionInfo").get("sessionId");if(s!=null)session=s.toString();}}
        catch(Exception e){uncertain=true;throw e;}
        if(child(result,"status").containsKey("errorResult"))throw new IOExceptionLike("BigQuery rejected the recorded job");if(create&&session==null)throw new IOExceptionLike("Session identifier is missing");return result;
    }
    public void insert(String table,String[] columns,Object[] values)throws Exception{
        if(columns.length!=values.length||new HashSet<>(Arrays.asList(columns)).size()!=columns.length)throw new IllegalArgumentException("INSERT mapping differs");Map<String,Object> defs=MfRuntime.obj(MfRuntime.obj(schema.get(table)).get("columns"));List<Object> bound=new ArrayList<>();for(int i=0;i<columns.length;i++)bound.add(exact(MfRuntime.obj(defs.get(columns[i])),values[i]));
        Map<String,Object> event=new LinkedHashMap<>();event.put("op","insert");event.put("table",table);event.put("columns",Arrays.asList(columns));event.put("values",bound);operations.add(event);
        if(contract){pending=true;return;}
        List<String> names=new ArrayList<>(),tokens=new ArrayList<>();for(int i=0;i<columns.length;i++){names.add(identifier(columns[i]));tokens.add(TARGET.equals("bigquery")?"@p"+i:"?");}String sql="INSERT INTO "+identifier(table)+" ("+String.join(",",names)+") VALUES ("+String.join(",",tokens)+")";
        if(TARGET.equals("bigquery")){if(!pending)query("BEGIN TRANSACTION;",List.of(),session==null);pending=true;List<Object> params=new ArrayList<>();for(int i=0;i<columns.length;i++){var c=MfRuntime.obj(defs.get(columns[i]));String k=(String)c.get("kind");String typ=k.equals("integer")?"INT64":k.equals("text")?"STRING":MfRuntime.integer(c.get("scale"))<=9&&MfRuntime.integer(c.get("precision"))-MfRuntime.integer(c.get("scale"))<=29?"NUMERIC":"BIGNUMERIC";Map<String,Object> value=new LinkedHashMap<>();if(bound.get(i)!=null)value.put("value",bound.get(i).toString());params.add(Map.of("name","p"+i,"parameterType",Map.of("type",typ),"parameterValue",value));}query(sql,params,false);}
        else{connect();pending=true;try(PreparedStatement command=conn.prepareStatement(sql)){for(int i=0;i<columns.length;i++){Object value=bound.get(i);var c=MfRuntime.obj(defs.get(columns[i]));if(value==null)command.setNull(i+1,c.get("kind").equals("text")?Types.VARCHAR:Types.NUMERIC);else if(c.get("kind").equals("integer"))command.setLong(i+1,(Long)value);else if(c.get("kind").equals("decimal")&&TARGET.equals("oracle"))command.setBigDecimal(i+1,new BigDecimal(value.toString()));else command.setString(i+1,value.toString());}command.executeUpdate();}}
    }
    public void commit()throws Exception{operations.add(Map.of("op","commit"));if(!contract){if(TARGET.equals("bigquery")&&pending)query("COMMIT TRANSACTION;",List.of(),false);else if(conn!=null)conn.commit();}pending=false;}
    public void rollback()throws Exception{operations.add(Map.of("op","rollback"));if(!contract){if(TARGET.equals("bigquery")&&pending)query("ROLLBACK TRANSACTION;",List.of(),false);else if(conn!=null)conn.rollback();}pending=false;}
    public void finish()throws Exception{if(pending){rollback();throw new IllegalStateException("Source ended with an uncommitted transaction; no commit was added");}}
    public void close()throws Exception{if(pending&&!uncertain)rollback();if(conn!=null)conn.close();if(TARGET.equals("bigquery")&&session!=null&&!contract&&!uncertain){query("CALL BQ.ABORT_SESSION();",List.of(),false);session=null;}}
}
