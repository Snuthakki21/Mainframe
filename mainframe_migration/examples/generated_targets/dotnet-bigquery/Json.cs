// Strict run-contract JSON, with exact decimal parsing and duplicate-key rejection.
using System;
using System.Collections.Generic;
using System.Text.Json;

public static class Json {
    public static object Parse(string text){using var doc=JsonDocument.Parse(text.TrimStart('\ufeff'));return Convert(doc.RootElement);}
    private static object Convert(JsonElement e){switch(e.ValueKind){case JsonValueKind.Object:var d=new Dictionary<string,object>();foreach(var p in e.EnumerateObject()){if(d.ContainsKey(p.Name))throw new FormatException("Duplicate JSON key");d[p.Name]=Convert(p.Value);}return d;case JsonValueKind.Array:var a=new List<object>();foreach(var x in e.EnumerateArray())a.Add(Convert(x));return a;case JsonValueKind.String:return e.GetString();case JsonValueKind.Number:return Dec.Parse(e.GetRawText());case JsonValueKind.True:return true;case JsonValueKind.False:return false;case JsonValueKind.Null:return null;default:throw new FormatException("Unsupported JSON token");}}
    public static string Dump(object value)=>JsonSerializer.Serialize(value,new JsonSerializerOptions{WriteIndented=true});
}
