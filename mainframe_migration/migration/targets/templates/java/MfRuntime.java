/* Native Java record and arithmetic behavior shared by generated job files.
 * This is not an interpreter for Python. Each source statement is generated in
 * its job class. Helpers retain fixed-width storage and explicit source rules.
 */
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.math.*;

public final class MfRuntime {
    public static final MathContext MC=new MathContext(80,RoundingMode.HALF_EVEN);
    // Contract objects are checked at the boundary rather than guessed.
    @SuppressWarnings("unchecked") public static Map<String,Object> obj(Object x){if(!(x instanceof Map))throw new IllegalArgumentException("Expected JSON object");return (Map<String,Object>)x;}
    @SuppressWarnings("unchecked") public static List<Object> list(Object x){if(!(x instanceof List))throw new IllegalArgumentException("Expected JSON array");return (List<Object>)x;}
    public static int integer(Object x){return num(x).intValueExact();}
    public static BigDecimal num(Object x){if(x instanceof BigDecimal n)return n;if(x instanceof String||x instanceof Integer||x instanceof Long)return new BigDecimal(x.toString());throw new IllegalArgumentException("Expected exact number");}
    // Perform decimal operations at the explicitly selected arithmetic precision.
    public static Object math(String op,Object a,Object b){BigDecimal x=num(a),y=num(b);return switch(op){case "+"->x.add(y,MC);case "-"->x.subtract(y,MC);case "*"->x.multiply(y,MC);case "/"->x.divide(y,MC);default->throw new IllegalArgumentException("Unknown arithmetic operation");};}
    public static boolean truth(Object x){if(x instanceof Boolean b)return b;if(x instanceof BigDecimal n)return n.signum()!=0;if(x instanceof String s)return !s.isEmpty();throw new IllegalArgumentException("Unsupported condition value");}
    public static byte[] encode(String text,String table){byte[] result=new byte[text.length()];for(int i=0;i<text.length();i++){int n=table.indexOf(text.charAt(i));if(n<0)throw new IllegalArgumentException("Character is not in the source code page");result[i]=(byte)n;}return result;}
    public static String decode(byte[] raw,String table){StringBuilder text=new StringBuilder();for(byte b:raw){int n=b&255;if(n>=table.length())throw new IllegalArgumentException("Byte is not in the source code page");text.append(table.charAt(n));}return text.toString();}
    public static int bytesCompare(byte[] a,byte[] b){for(int i=0;i<Math.min(a.length,b.length);i++){int c=Integer.compare(a[i]&255,b[i]&255);if(c!=0)return c;}return Integer.compare(a.length,b.length);}
    public static String pad(String s,int n){return s.length()>=n?s.substring(0,n):s+" ".repeat(n-s.length());}
    // A reference identifies the caller's live storage, not an eagerly read value.
    public static final class Ref {final Fields owner;final String name;Ref(Fields owner,String name){this.owner=owner;this.name=name;}}
    public static final class Storage {final char[] data;final int offset;Storage(char[] data,int offset){this.data=data;this.offset=offset;}}
    public static final class Fields {
        final Map<String,Map<String,Object>> layout=new LinkedHashMap<>();final Map<String,char[]> buffers=new HashMap<>();final Map<String,Ref> aliases=new HashMap<>();
        // Build group and child fields over the same character buffers.
        public Fields(List<Object> definitions){for(Object x:definitions){var f=obj(x);String name=(String)f.get("name"),root=(String)f.get("root");layout.put(name,f);int size=integer(f.get("offset"))+integer(f.get("length"));char[] old=buffers.get(root);if(old==null||old.length<size){char[] n=new char[size];Arrays.fill(n,' ');if(old!=null)System.arraycopy(old,0,n,0,old.length);buffers.put(root,n);}}
            for(var f:layout.values())if(f.get("kind").equals("number"))set((String)f.get("name"),BigDecimal.ZERO);
            for(var f:layout.values())if(f.containsKey("value"))set((String)f.get("name"),f.get("value"));}
        private Storage storage(String name){var f=layout.get(name);if(f==null)throw new IllegalArgumentException("Unknown source field "+name);String root=(String)f.get("root");int offset=integer(f.get("offset"));if(aliases.containsKey(root)){Ref r=aliases.get(root);Storage s=r.owner.storage(r.name);return new Storage(s.data,s.offset+offset);}return new Storage(buffers.get(root),offset);}
        public int length(String name){return integer(layout.get(name).get("length"));}
        public String raw(String name){Storage s=storage(name);return new String(s.data,s.offset,length(name));}
        public Object get(String name){String text=raw(name);var f=layout.get(name);if(!f.get("kind").equals("number"))return text;if(!text.matches("[0-9]+"))throw new IllegalArgumentException("Nonnumeric source field "+name);return new BigDecimal(text).scaleByPowerOfTen(-integer(f.get("scale")));}
        // Apply receiving-picture truncation and low-order overflow exactly as defined by the supported model.
        public void set(String name,Object value){var f=layout.get(name);int length=length(name);String text;if(f.get("kind").equals("number")){BigInteger number=num(value).abs().scaleByPowerOfTen(integer(f.get("scale"))).toBigInteger();text=number.mod(BigInteger.TEN.pow(length)).toString();text="0".repeat(length-text.length())+text;}else text=pad(value.toString(),length);Storage s=storage(name);text.getChars(0,length,s.data,s.offset);}
        public Ref reference(String name){storage(name);return new Ref(this,name);}
        public void bind(String name,Ref r){var f=layout.get(name);if(!f.get("root").equals(name)||integer(f.get("offset"))!=0||length(name)!=r.owner.length(r.name))throw new IllegalArgumentException("Source CALL linkage differs in width/root");aliases.put(name,r);}
    }
    public static final class RecordFile {
        final InputStream input;final OutputStream output;final String table;final int length;boolean closed=false;
        // Fixed records are binary streams; platform line endings never alter their contents.
        RecordFile(Path path,String mode,String table,int length)throws IOException{this.table=table;this.length=length;if(mode.equals("INPUT")){input=Files.newInputStream(path);output=null;}else if(mode.equals("OUTPUT")){Files.createDirectories(path.getParent());output=Files.newOutputStream(path);input=null;}else throw new IllegalArgumentException("Unsupported OPEN mode");}
        public String read()throws IOException{if(input==null)throw new IllegalStateException("File is not open for input");byte[] raw=input.readNBytes(length);if(raw.length==0)return null;if(raw.length!=length)throw new IOException("Input ends with a partial record");return decode(raw,table);}
        public void write(String text)throws IOException{byte[] raw=encode(text,table);if(output==null||raw.length!=length)throw new IOException("Output record length/mode differs from source");output.write(raw);}
        public void close()throws IOException{if(closed)return;if(input!=null)input.close();if(output!=null)output.close();closed=true;}
    }
    public static final class Context implements AutoCloseable {
        public final Map<String,Object> payload;public final Map<String,Integer> events=new LinkedHashMap<>();public final MfDatabase db;
        final Map<String,Object> datasets,tables;final List<RecordFile> opened=new ArrayList<>();final Path caseRoot,workRoot;final String encoding;
        public Context(Map<String,Object> p)throws Exception{payload=p;datasets=obj(p.get("datasets"));tables=obj(p.get("codepages"));encoding=(String)p.get("collation");caseRoot=Path.of((String)p.get("case_root")).toRealPath();workRoot=Path.of((String)p.get("work_root")).toRealPath();db=new MfDatabase(p);}
        public void hit(String id){events.merge(id,1,Integer::sum);}
        public List<Object> layout(String program){for(Object m:list(payload.get("models"))){var model=obj(m);if(!model.get("job").equals(payload.get("job")))continue;for(Object p:list(model.get("programs"))){var spec=obj(p);if(spec.get("name").equals(program))return list(spec.get("layout"));}}throw new IllegalArgumentException("Program layout is missing");}
        public Map<String,Object> dd(String job,String step){for(Object m:list(payload.get("models"))){var model=obj(m);if(!model.get("job").equals(job))continue;for(Object s:list(model.get("steps"))){var spec=obj(s);if(spec.get("name").equals(step))return obj(spec.get("dds"));}}throw new IllegalArgumentException("Step bindings are missing");}
        private Path inside(Path root,String relative)throws IOException{Path rel=Path.of(relative);if(rel.isAbsolute()||relative.contains(":"))throw new IOException("Dataset path is not relative");for(Path p:rel)if(p.toString().equals(".."))throw new IOException("Dataset path leaves the managed area");Path out=root.resolve(rel).normalize();if(!out.startsWith(root))throw new IOException("Dataset path leaves the managed area");Path check=out;while(check!=null&&!check.equals(root)){if(Files.isSymbolicLink(check))throw new IOException("Dataset symbolic links are not accepted");check=check.getParent();}return out;}
        public RecordFile open(Map<String,Object> dd,String mode,int length)throws Exception{var spec=obj(datasets.get(dd.get("dsn")));if(!spec.get("format").equals("fixed")||integer(spec.get("record_length"))!=length)throw new IllegalArgumentException("Dataset layout differs from source");boolean input=spec.get("role").equals("input");if(input&&mode.equals("OUTPUT"))throw new IllegalArgumentException("Input dataset cannot be overwritten");Path path=inside(input?caseRoot:workRoot,(String)spec.get("path"));RecordFile f=new RecordFile(path,mode,(String)tables.get(spec.get("encoding")),length);opened.add(f);return f;}
        public boolean relation(Object a,String op,Object b){int c;if(a instanceof String&&b instanceof String){String x=(String)a,y=(String)b;int n=Math.max(x.length(),y.length());String table=(String)tables.get(encoding);c=bytesCompare(encode(pad(x,n),table),encode(pad(y,n),table));}else c=num(a).compareTo(num(b));return switch(op){case "="->c==0;case "<>"->c!=0;case ">"->c>0;case "<"->c<0;case ">="->c>=0;case "<="->c<=0;default->throw new IllegalArgumentException("Unknown comparison");};}
        public void copy(Map<String,Object> source,Map<String,Object> target)throws Exception{int n=integer(obj(datasets.get(source.get("dsn"))).get("record_length"));RecordFile r=open(source,"INPUT",n),w=open(target,"OUTPUT",n);String text;while((text=r.read())!=null)w.write(text);r.close();w.close();}
        // List.sort is stable; equal keys retain their source input order, including duplicates.
        public void sort(Map<String,Object> source,Map<String,Object> target,int[][] keys)throws Exception{var spec=obj(datasets.get(source.get("dsn")));int n=integer(spec.get("record_length"));RecordFile r=open(source,"INPUT",n);List<String> rows=new ArrayList<>();String text;int limit=integer(payload.getOrDefault("max_sort_records",100000));while((text=r.read())!=null){rows.add(text);if(rows.size()>limit)throw new IllegalArgumentException("Local sort record limit exceeded");}r.close();String table=(String)tables.get(spec.get("encoding"));for(int ki=keys.length-1;ki>=0;ki--){int[] key=keys[ki];rows.sort((a,b)->{if(key[0]-1+key[1]>a.length()||key[0]-1+key[1]>b.length())throw new IllegalArgumentException("Sort key extends past record");String x=a.substring(key[0]-1,key[0]-1+key[1]),y=b.substring(key[0]-1,key[0]-1+key[1]);int c;if(key[2]==0)c=bytesCompare(encode(x,table),encode(y,table));else{if(!x.matches("[0-9]+")||!y.matches("[0-9]+"))throw new IllegalArgumentException("Nonnumeric ZD sort key");c=new BigDecimal(x).compareTo(new BigDecimal(y));}return key[3]==1?-c:c;});}RecordFile w=open(target,"OUTPUT",n);for(String row:rows)w.write(row);w.close();}
        public void insert(String table,String[] columns,Object[] values)throws Exception{db.insert(table,columns,values);}
        public void commit()throws Exception{db.commit();}
        public void rollback()throws Exception{db.rollback();}
        public void finish()throws Exception{db.finish();}
        public void end_step()throws Exception{finish();for(RecordFile f:opened)f.close();opened.clear();}
        public void close()throws Exception{try{for(RecordFile f:opened)f.close();}finally{db.close();}}
    }
}
