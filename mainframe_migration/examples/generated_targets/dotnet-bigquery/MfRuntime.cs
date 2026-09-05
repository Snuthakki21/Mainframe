// Native C# helpers preserve source storage, record bytes, aliases and arithmetic.
// Source statements execute in generated job functions, not in another language.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;

public static class MfRuntime {
    public static Dictionary<string,object> obj(object x)=>x as Dictionary<string,object> ?? throw new ArgumentException("Expected JSON object");
    public static List<object> list(object x)=>x as List<object> ?? throw new ArgumentException("Expected JSON array");
    public static Dec num(object x){if(x is Dec n)return n;if(x is string s)return Dec.Parse(s);if(x is int||x is long)return Dec.Parse(x.ToString());throw new ArgumentException("Expected exact number");}
    public static int integer(object x)=>num(x).ToInt32();
    public static object math(string op,object a,object b)=>Dec.Math(op,num(a),num(b));
    public static bool truth(object x)=>x is bool b?b:x is Dec n?!n.N.IsZero:x is string s?s.Length>0:throw new ArgumentException("Unsupported condition value");
    public static string pad(string s,int n)=>s.Length>=n?s.Substring(0,n):s.PadRight(n,' ');
    public static byte[] encode(string text,string table){var data=new byte[text.Length];for(int i=0;i<text.Length;i++){int n=table.IndexOf(text[i]);if(n<0)throw new ArgumentException("Character is outside source code page");data[i]=(byte)n;}return data;}
    public static string decode(byte[] data,string table){var result=new char[data.Length];for(int i=0;i<data.Length;i++){if(data[i]>=table.Length)throw new ArgumentException("Byte is outside source code page");result[i]=table[data[i]];}return new string(result);}
    public static int bytesCompare(byte[] a,byte[] b){for(int i=0;i<Math.Min(a.Length,b.Length);i++){int c=a[i].CompareTo(b[i]);if(c!=0)return c;}return a.Length.CompareTo(b.Length);}
    public sealed class Ref {public Fields Owner;public string Name;public Ref(Fields owner,string name){Owner=owner;Name=name;}}
    public sealed class Fields {
        readonly Dictionary<string,Dictionary<string,object>> layout=new();readonly Dictionary<string,char[]> buffers=new();readonly Dictionary<string,Ref> aliases=new();
        // Store groups and individual fields in the same underlying characters.
        public Fields(List<object> definitions){foreach(var x in definitions){var f=obj(x);string name=(string)f["name"],root=(string)f["root"];layout.Add(name,f);int size=integer(f["offset"])+integer(f["length"]);if(!buffers.TryGetValue(root,out var old)||old.Length<size){var next=Enumerable.Repeat(' ',size).ToArray();if(old!=null)Array.Copy(old,next,old.Length);buffers[root]=next;}}
            foreach(var f in layout.Values)if((string)f["kind"]=="number")set((string)f["name"],Dec.Zero);foreach(var f in layout.Values)if(f.ContainsKey("value"))set((string)f["name"],f["value"]);}
        (char[],int) storage(string name){var f=layout[name];string root=(string)f["root"];int offset=integer(f["offset"]);if(aliases.TryGetValue(root,out var r)){var (data,start)=r.Owner.storage(r.Name);return(data,start+offset);}return(buffers[root],offset);}
        public int length(string name)=>integer(layout[name]["length"]);
        public string raw(string name){var(data,start)=storage(name);return new string(data,start,length(name));}
        public object get(string name){string text=raw(name);var f=layout[name];if((string)f["kind"]!="number")return text;if(text.Length==0||text.Any(c=>c<'0'||c>'9'))throw new ArgumentException("Nonnumeric source field "+name);int scale=integer(f["scale"]);if(scale>0)text=text.Insert(text.Length-scale,".");return Dec.Parse(text);}
        // Use the receiving picture's low-order digits; never replace this with banker's rounding.
        public void set(string name,object value){var f=layout[name];int n=length(name);string text;if((string)f["kind"]=="number"){var number=BigInteger.Abs(num(value).Truncated(integer(f["scale"])));text=(number%BigInteger.Pow(10,n)).ToString().PadLeft(n,'0');}else text=pad(value.ToString(),n);var(data,start)=storage(name);text.CopyTo(0,data,start,n);}
        public Ref reference(string name){storage(name);return new Ref(this,name);}
        public void bind(string name,Ref reference){var f=layout[name];if((string)f["root"]!=name||integer(f["offset"])!=0||length(name)!=reference.Owner.length(reference.Name))throw new ArgumentException("Source CALL linkage differs in width/root");aliases[name]=reference;}
    }
    public sealed class RecordFile {
        readonly FileStream stream;readonly string mode,table;readonly int length;bool closed;
        public RecordFile(string path,string mode,string table,int length){this.mode=mode;this.table=table;this.length=length;if(mode=="OUTPUT")Directory.CreateDirectory(Path.GetDirectoryName(path));if(mode!="INPUT"&&mode!="OUTPUT")throw new ArgumentException("Unsupported file mode");stream=new FileStream(path,mode=="INPUT"?FileMode.Open:FileMode.Create,mode=="INPUT"?FileAccess.Read:FileAccess.Write);}
        public string read(){if(mode!="INPUT")throw new IOException("File is not open for input");var raw=new byte[length];int got=0,n;while(got<length&&(n=stream.Read(raw,got,length-got))>0)got+=n;if(got==0)return null;if(got!=length)throw new IOException("Input ends with a partial record");return decode(raw,table);}
        public void write(string text){var raw=encode(text,table);if(mode!="OUTPUT"||raw.Length!=length)throw new IOException("Output record length/mode differs from source");stream.Write(raw,0,raw.Length);}
        public void close(){if(closed)return;stream.Dispose();closed=true;}
    }
    public sealed class Context : IDisposable {
        public readonly Dictionary<string,object> payload;public readonly Dictionary<string,int> events=new();public readonly MfDatabase db;
        readonly Dictionary<string,object> datasets,tables;readonly List<RecordFile> opened=new();readonly string caseRoot,workRoot,encoding;
        public Context(Dictionary<string,object> p){payload=p;datasets=obj(p["datasets"]);tables=obj(p["codepages"]);encoding=(string)p["collation"];caseRoot=Path.GetFullPath((string)p["case_root"]);workRoot=Path.GetFullPath((string)p["work_root"]);db=new MfDatabase(p);}
        public void hit(string id){events[id]=events.GetValueOrDefault(id,0)+1;}
        public List<object> layout(string program){foreach(var m in list(payload["models"])){var model=obj(m);if((string)model["job"]!=(string)payload["job"])continue;foreach(var p in list(model["programs"])){var spec=obj(p);if((string)spec["name"]==program)return list(spec["layout"]);}}throw new ArgumentException("Program layout is missing");}
        public Dictionary<string,object> dd(string job,string step){foreach(var m in list(payload["models"])){var model=obj(m);if((string)model["job"]!=job)continue;foreach(var s in list(model["steps"])){var spec=obj(s);if((string)spec["name"]==step)return obj(spec["dds"]);}}throw new ArgumentException("Step bindings are missing");}
        string inside(string root,string relative){if(Path.IsPathRooted(relative)||relative.Contains(':')||relative.Replace('\\','/').Split('/').Contains(".."))throw new IOException("Dataset path leaves managed area");string full=Path.GetFullPath(Path.Combine(root,relative)),rel=Path.GetRelativePath(root,full);if(rel==".."||rel.StartsWith(".."+Path.DirectorySeparatorChar))throw new IOException("Dataset path leaves managed area");string at=full;while(at!=root&&at!=null){if((File.Exists(at)||Directory.Exists(at))&&(File.GetAttributes(at)&FileAttributes.ReparsePoint)!=0)throw new IOException("Dataset reparse links are not accepted");at=Path.GetDirectoryName(at);}return full;}
        public RecordFile open(Dictionary<string,object> dd,string mode,int length){var spec=obj(datasets[(string)dd["dsn"]]);if((string)spec["format"]!="fixed"||integer(spec["record_length"])!=length)throw new ArgumentException("Dataset layout differs from source");bool input=(string)spec["role"]=="input";if(input&&mode=="OUTPUT")throw new ArgumentException("Input dataset cannot be overwritten");var f=new RecordFile(inside(input?caseRoot:workRoot,(string)spec["path"]),mode,(string)tables[(string)spec["encoding"]],length);opened.Add(f);return f;}
        public bool relation(object a,string op,object b){int c;if(a is string x&&b is string y){int n=Math.Max(x.Length,y.Length);string table=(string)tables[encoding];c=bytesCompare(encode(pad(x,n),table),encode(pad(y,n),table));}else c=num(a).CompareTo(num(b));return op switch{"="=>c==0,"<>"=>c!=0,">"=>c>0,"<"=>c<0,">="=>c>=0,"<="=>c<=0,_=>throw new ArgumentException("Unknown comparison")};}
        public void copy(Dictionary<string,object> source,Dictionary<string,object> target){int n=integer(obj(datasets[(string)source["dsn"]])["record_length"]);var r=open(source,"INPUT",n);var w=open(target,"OUTPUT",n);string text;while((text=r.read())!=null)w.write(text);r.close();w.close();}
        // OrderBy is used deliberately: List.Sort does not promise stable equal-key order.
        public void sort(Dictionary<string,object> source,Dictionary<string,object> target,int[][] keys){var spec=obj(datasets[(string)source["dsn"]]);int n=integer(spec["record_length"]);var r=open(source,"INPUT",n);var rows=new List<string>();string text;int limit=integer(payload.GetValueOrDefault("max_sort_records",100000));while((text=r.read())!=null){rows.Add(text);if(rows.Count>limit)throw new ArgumentException("Local sort record limit exceeded");}r.close();string table=(string)tables[(string)spec["encoding"]];for(int ki=keys.Length-1;ki>=0;ki--){var key=keys[ki];var cmp=Comparer<string>.Create((a,b)=>{if(key[0]-1+key[1]>a.Length||key[0]-1+key[1]>b.Length)throw new ArgumentException("Sort key extends past record");string x=a.Substring(key[0]-1,key[1]),y=b.Substring(key[0]-1,key[1]);int c;if(key[2]==0)c=bytesCompare(encode(x,table),encode(y,table));else{if(x.Any(v=>v<'0'||v>'9')||y.Any(v=>v<'0'||v>'9'))throw new ArgumentException("Nonnumeric ZD sort key");c=Dec.Parse(x).CompareTo(Dec.Parse(y));}return key[3]==1?-c:c;});rows=rows.OrderBy(x=>x,cmp).ToList();}var w=open(target,"OUTPUT",n);foreach(string row in rows)w.write(row);w.close();}
        public void insert(string table,string[] columns,object[] values)=>db.insert(table,columns,values);
        public void commit()=>db.commit();public void rollback()=>db.rollback();public void finish()=>db.finish();
        public void end_step(){finish();foreach(var f in opened)f.close();opened.Clear();}
        public void Dispose(){try{foreach(var f in opened)f.close();}finally{db.Dispose();}}
    }
}
