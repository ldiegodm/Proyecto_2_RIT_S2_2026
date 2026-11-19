package paleobusca.normalizacion;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.regex.MatchResult;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Etapa de texto de la normalizacion (pasos 1 a 10 de ESPECIFICACION.md). Es la traduccion directa
 * de Normalizador.preprocesar() en Python: mismas expresiones regulares y mismo orden.
 * No se usan \s, \d, \w ni \b para que el comportamiento no dependa del motor de expresiones.
 */
public final class Preprocesador {

    static final String WS = "[ \\t\\n\\x0b\\f\\r]";
    static final String NO_PAL_ANTES = "(?<![a-z0-9_])";
    static final String NO_PAL_DESPUES = "(?![a-z0-9_])";

    static final Pattern COMILLAS = Pattern.compile("[\\u2018\\u2019\\u201a\\u201b\\u2032\\u02bc`]");
    static final Pattern GUIONES = Pattern.compile("[\\u2010\\u2011\\u2012\\u2013\\u2014\\u2015\\u2212]");
    static final Pattern GUION_FIN_LINEA = Pattern.compile("([a-z])-[ \\t]*\\r?\\n[ \\t]*([a-z])");
    static final Pattern MARCAS = Pattern.compile("\\p{Mn}");
    static final Pattern POSESIVO = Pattern.compile("'s" + NO_PAL_DESPUES);
    static final Pattern APOSTROFO_INTERNO = Pattern.compile("(?<=[a-z0-9])'(?=[a-z0-9])");

    static final Map<String, Integer> NUM_MES = new LinkedHashMap<>();
    static {
        String[] meses = {"january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december"};
        for (int i = 0; i < meses.length; i++) NUM_MES.put(meses[i], i + 1);
        NUM_MES.putAll(Map.of("jan", 1, "feb", 2, "mar", 3, "apr", 4, "jun", 6, "jul", 7, "aug", 8,
                "sept", 9, "sep", 9, "oct", 10));
        NUM_MES.put("nov", 11);
        NUM_MES.put("dec", 12);
    }
    static final Comparator<String> MAS_LARGO_PRIMERO =
            Comparator.comparingInt(String::length).reversed().thenComparing(Comparator.naturalOrder());
    static final String MES;
    static {
        List<String> m = new ArrayList<>(NUM_MES.keySet());
        m.sort(MAS_LARGO_PRIMERO);
        MES = NO_PAL_ANTES + "(" + String.join("|", m) + ")\\.?";
    }
    static final String DIA = "([0-9]{1,2})(?:st|nd|rd|th)?";
    static final String ANIO = "([0-9]{4})(?![0-9])";
    static final Pattern FECHA_ISO = Pattern.compile("(?<![0-9])([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?![0-9])");
    static final Pattern FECHA_DMA = Pattern.compile("(?<![a-z0-9_.])" + DIA + WS + "+" + MES + ",?" + WS + "+" + ANIO);
    static final Pattern FECHA_MDA = Pattern.compile(MES + WS + "+" + DIA + ",?" + WS + "+" + ANIO);
    static final Pattern FECHA_MA = Pattern.compile(MES + ",?" + WS + "+" + ANIO);

    static final Pattern MILES = Pattern.compile("(?<=[0-9]),(?=[0-9]{3}(?![0-9]))");

    static final String NUM = "(?<![a-z0-9_.])([0-9]+(?:\\.[0-9]+)?)[ \\t\\n\\x0b\\f\\r-]*";
    static final String SEP = "[ \\t\\n\\x0b\\f\\r-]+";
    static final String ANIOS = "years?(?:" + SEP + "(?:ago|old))?";
    static final Pattern GEO_GA = Pattern.compile(NUM + "(?:billion" + SEP + ANIOS + "|bya|gya|ga)" + NO_PAL_DESPUES);
    static final Pattern GEO_MA = Pattern.compile(NUM + "(?:million" + SEP + ANIOS + "|myr|mya|ma)" + NO_PAL_DESPUES);
    static final Pattern GEO_KA = Pattern.compile(NUM + "(?:thousand" + SEP + ANIOS + "|kyr|kya|ka)" + NO_PAL_DESPUES);

    static final Pattern WS_MAS = Pattern.compile(WS + "+");

    private final ConfigNormalizacion c;
    private final Pattern multi;
    private final Map<String, String> multiPorClave = new HashMap<>();

    public Preprocesador(ConfigNormalizacion config) {
        this.c = config;
        if (config.multipalabras.isEmpty()) {
            multi = null;
        } else {
            List<String> frases = new ArrayList<>(config.multipalabras.keySet());
            frases.sort(MAS_LARGO_PRIMERO);
            List<String> alternativas = new ArrayList<>();
            for (String f : frases) {
                alternativas.add(patronFrase(f));
                multiPorClave.put(String.join(" ", WS_MAS.split(f.strip())), config.multipalabras.get(f));
            }
            multi = Pattern.compile(NO_PAL_ANTES + "(?:" + String.join("|", alternativas) + ")" + NO_PAL_DESPUES);
        }
    }

    static String escaparLiteral(String texto) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < texto.length(); i++) {
            char ch = texto.charAt(i);
            if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) sb.append(ch);
            else sb.append('\\').append(ch);
        }
        return sb.toString();
    }

    static String patronFrase(String frase) {
        List<String> partes = new ArrayList<>();
        for (String p : WS_MAS.split(frase.strip())) if (!p.isEmpty()) partes.add(escaparLiteral(p));
        return String.join(WS + "+", partes);
    }

    public String preprocesar(String texto) {
        if (c.nfkc) texto = Normalizer.normalize(texto, Normalizer.Form.NFKC);                    // 1
        texto = COMILLAS.matcher(texto).replaceAll("'");                                          // 2
        texto = GUIONES.matcher(texto).replaceAll("-");
        texto = texto.toLowerCase(Locale.ROOT);                                                   // 3
        if (c.unirGuiones) texto = GUION_FIN_LINEA.matcher(texto).replaceAll("$1$2");             // 4
        if (c.plegarDiacriticos) texto = plegar(texto);                                           // 5
        texto = POSESIVO.matcher(texto).replaceAll("");                                           // 6
        texto = APOSTROFO_INTERNO.matcher(texto).replaceAll("");
        if (c.fechas) texto = fechas(texto);                                                      // 7
        if (c.numeros.equals("normalizar")) texto = MILES.matcher(texto).replaceAll("");          // 8
        if (c.fechasGeologicas) {                                                                 // 9
            texto = GEO_GA.matcher(texto).replaceAll("$1ga");
            texto = GEO_MA.matcher(texto).replaceAll("$1ma");
            texto = GEO_KA.matcher(texto).replaceAll("$1ka");
        }
        if (multi != null) {                                                                      // 10
            texto = reemplazar(multi, texto, m -> multiPorClave.get(String.join(" ", WS_MAS.split(m.group()))));
        }
        return texto;
    }

    private String plegar(String texto) {
        if (texto.chars().allMatch(ch -> ch < 128)) return texto;
        texto = MARCAS.matcher(Normalizer.normalize(texto, Normalizer.Form.NFD)).replaceAll("");
        if (c.plegado.isEmpty()) return texto;
        StringBuilder sb = new StringBuilder(texto.length());
        texto.codePoints().forEach(cp -> {
            String r = c.plegado.get(cp);
            if (r != null) sb.append(r);
            else sb.appendCodePoint(cp);
        });
        return sb.toString();
    }

    private static String fecha(int anio, int mes, Integer dia) {
        if (mes < 1 || mes > 12) return null;
        if (dia == null) return String.format("%d%02d", anio, mes);
        if (dia < 1 || dia > 31) return null;
        return String.format("%d%02d%02d", anio, mes, dia);
    }

    private static String o(String valor, MatchResult m) {
        return valor != null ? valor : m.group();
    }

    static String fechas(String texto) {
        texto = reemplazar(FECHA_ISO, texto, m -> o(fecha(Integer.parseInt(m.group(1)),
                Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3))), m));
        texto = reemplazar(FECHA_DMA, texto, m -> o(fecha(Integer.parseInt(m.group(3)),
                NUM_MES.get(m.group(2)), Integer.parseInt(m.group(1))), m));
        texto = reemplazar(FECHA_MDA, texto, m -> o(fecha(Integer.parseInt(m.group(3)),
                NUM_MES.get(m.group(1)), Integer.parseInt(m.group(2))), m));
        return reemplazar(FECHA_MA, texto, m -> o(fecha(Integer.parseInt(m.group(2)),
                NUM_MES.get(m.group(1)), null), m));
    }

    /** Como re.sub(patron, funcion, texto) de Python: el resultado de la funcion es literal. */
    private static String reemplazar(Pattern p, String texto, Function<MatchResult, String> f) {
        Matcher m = p.matcher(texto);
        return m.replaceAll(r -> Matcher.quoteReplacement(f.apply(r)));
    }
}
