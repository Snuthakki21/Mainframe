/* Small strict JSON reader/writer for the generated run contract.
 * No external library or floating-point parser is needed. Numbers remain decimal.
 */
import java.util.*;
import java.math.BigDecimal;

public final class Json {
    // Read one complete JSON document, rejecting duplicate keys and trailing text.
    public static Object parse(String text) {
        Parser p=new Parser(text.startsWith("\ufeff")?text.substring(1):text);
        Object value=p.value();p.ws();if(p.i!=p.s.length())throw new IllegalArgumentException("Trailing JSON text");return value;
    }
    // Write JSON without narrowing exact numbers to floating point.
    public static String dump(Object value) {
        if(value==null)return "null";
        if(value instanceof String s){StringBuilder b=new StringBuilder("\"");for(char c:s.toCharArray()){
            switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<32||c>126)b.append(String.format("\\u%04x",(int)c));else b.append(c);}}
            return b.append('"').toString();}
        if(value instanceof Boolean||value instanceof Number)return value.toString();
        if(value instanceof Map<?,?> map){List<String> rows=new ArrayList<>();for(var e:map.entrySet())rows.add(dump(e.getKey().toString())+":"+dump(e.getValue()));return "{"+String.join(",",rows)+"}";}
        if(value instanceof Iterable<?> list){List<String> rows=new ArrayList<>();for(Object x:list)rows.add(dump(x));return "["+String.join(",",rows)+"]";}
        if(value instanceof Object[] list)return dump(Arrays.asList(list));
        throw new IllegalArgumentException("Unsupported JSON value: "+value.getClass());
    }
    private static final class Parser {
        final String s;int i=0;
        Parser(String s){this.s=s;}
        void ws(){while(i<s.length()&&" \t\r\n".indexOf(s.charAt(i))>=0)i++;}
        char take(){if(i>=s.length())throw new IllegalArgumentException("Unexpected end of JSON");return s.charAt(i++);}
        Object value(){ws();if(i>=s.length())throw new IllegalArgumentException("Missing JSON value");char c=s.charAt(i);
            if(c=='"')return string();
            if(c=='{'){i++;Map<String,Object> m=new LinkedHashMap<>();ws();if(i<s.length()&&s.charAt(i)=='}'){i++;return m;}while(true){ws();if(i>=s.length()||s.charAt(i)!='"')throw new IllegalArgumentException("Object key needs quotes");String key=string();ws();if(take()!=':')throw new IllegalArgumentException("Missing colon");if(m.containsKey(key))throw new IllegalArgumentException("Duplicate JSON key");m.put(key,value());ws();char end=take();if(end=='}')return m;if(end!=',')throw new IllegalArgumentException("Missing comma");}}
            if(c=='['){i++;List<Object> a=new ArrayList<>();ws();if(i<s.length()&&s.charAt(i)==']'){i++;return a;}while(true){a.add(value());ws();char end=take();if(end==']')return a;if(end!=',')throw new IllegalArgumentException("Missing comma");}}
            if(s.startsWith("true",i)){i+=4;return true;}if(s.startsWith("false",i)){i+=5;return false;}if(s.startsWith("null",i)){i+=4;return null;}
            int start=i;while(i<s.length()&&"-+0123456789.eE".indexOf(s.charAt(i))>=0)i++;
            String token=s.substring(start,i);if(!token.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?"))throw new IllegalArgumentException("Invalid JSON number");return new BigDecimal(token);
        }
        String string(){if(take()!='"')throw new IllegalArgumentException("Missing quote");StringBuilder b=new StringBuilder();while(true){char c=take();if(c=='"')return b.toString();if(c<32)throw new IllegalArgumentException("Control character in JSON");if(c!='\\'){b.append(c);continue;}char e=take();switch(e){case '"':case '\\':case '/':b.append(e);break;case 'b':b.append('\b');break;case 'f':b.append('\f');break;case 'n':b.append('\n');break;case 'r':b.append('\r');break;case 't':b.append('\t');break;case 'u':if(i+4>s.length())throw new IllegalArgumentException("Short unicode escape");b.append((char)Integer.parseInt(s.substring(i,i+4),16));i+=4;break;default:throw new IllegalArgumentException("Invalid JSON escape");}}}
    }
}
