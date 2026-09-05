// Exact decimal arithmetic for the supported source profile.
// Ordinary C# decimal is not substituted for 31-digit COBOL fields. BigInteger
// fractions are rounded to 80 significant decimal digits after each operation.
using System;
using System.Globalization;
using System.Numerics;
using System.Text.RegularExpressions;

public sealed class Dec : IComparable<Dec> {
    public BigInteger N { get; }
    public BigInteger D { get; }
    public static readonly Dec Zero=new Dec(BigInteger.Zero,BigInteger.One);
    private Dec(BigInteger n,BigInteger d){if(d.IsZero)throw new DivideByZeroException();if(d.Sign<0){n=-n;d=-d;}var g=BigInteger.GreatestCommonDivisor(BigInteger.Abs(n),d);N=n/g;D=d/g;}
    // Parse source values without converting through binary floating point.
    public static Dec Parse(string text){var m=Regex.Match(text,@"^([+-]?)([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$");if(!m.Success)throw new FormatException("Not an exact decimal");string digits=m.Groups[2].Value+m.Groups[3].Value;var n=BigInteger.Parse(digits,CultureInfo.InvariantCulture);if(m.Groups[1].Value=="-")n=-n;int scale=m.Groups[3].Length-(m.Groups[4].Success?int.Parse(m.Groups[4].Value,CultureInfo.InvariantCulture):0);if(System.Math.Abs(scale)>10000)throw new FormatException("Decimal exponent exceeds the profile limit");return scale>=0?new Dec(n,BigInteger.Pow(10,scale)):new Dec(n*BigInteger.Pow(10,-scale),1);}
    private static int Digits(BigInteger n)=>BigInteger.Abs(n).ToString(CultureInfo.InvariantCulture).Length;
    // Use round-half-even at the same 80-digit precision as Python/Java helpers.
    private static Dec Rounded(BigInteger n,BigInteger d){if(d.IsZero)throw new DivideByZeroException();if(n.IsZero)return Zero;if(d.Sign<0){n=-n;d=-d;}int sign=n.Sign;var a=BigInteger.Abs(n);int exp=Digits(a)-Digits(d);bool below=exp>=0?a<d*BigInteger.Pow(10,exp):a*BigInteger.Pow(10,-exp)<d;if(below)exp--;int scale=79-exp;var top=scale>=0?a*BigInteger.Pow(10,scale):a;var bottom=scale>=0?d:d*BigInteger.Pow(10,-scale);var q=BigInteger.DivRem(top,bottom,out var rem);int cmp=(rem*2).CompareTo(bottom);if(cmp>0||(cmp==0&&!q.IsEven))q++;q*=sign;return scale>=0?new Dec(q,BigInteger.Pow(10,scale)):new Dec(q*BigInteger.Pow(10,-scale),1);}
    public static Dec Math(string op,Dec a,Dec b)=>op switch {"+"=>Rounded(a.N*b.D+b.N*a.D,a.D*b.D),"-"=>Rounded(a.N*b.D-b.N*a.D,a.D*b.D),"*"=>Rounded(a.N*b.N,a.D*b.D),"/"=>Rounded(a.N*b.D,a.D*b.N),_=>throw new ArgumentException("Unknown arithmetic operation")};
    public int CompareTo(Dec other)=>(N*other.D).CompareTo(other.N*D);
    public BigInteger Truncated(int scale)=>N*BigInteger.Pow(10,scale)/D;
    public bool IsInteger=>(N%D).IsZero;
    public long ToInt64(){if(!IsInteger)throw new InvalidOperationException("Fractional integer");return checked((long)(N/D));}
    public int ToInt32()=>checked((int)ToInt64());
    public string Fixed(int scale){var scaled=N*BigInteger.Pow(10,scale);var q=BigInteger.DivRem(scaled,D,out var rem);if(!rem.IsZero)throw new InvalidOperationException("Source decimal needs explicit rounding before database insert");string s=BigInteger.Abs(q).ToString(CultureInfo.InvariantCulture).PadLeft(scale+1,'0');if(scale>0)s=s.Insert(s.Length-scale,".");return q.Sign<0?"-"+s:s;}
    public override string ToString(){if(N.IsZero)return "0";BigInteger den=D;int twos=0,fives=0;while((den%2).IsZero){den/=2;twos++;}while((den%5).IsZero){den/=5;fives++;}if(den!=1)throw new InvalidOperationException("Non-terminating internal decimal");return Fixed(System.Math.Max(twos,fives));}
}
