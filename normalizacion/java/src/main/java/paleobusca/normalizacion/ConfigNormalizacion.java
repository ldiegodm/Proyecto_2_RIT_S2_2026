package paleobusca.normalizacion;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Perfil de normalizacion leido de un archivo .conf (formato INI de Linux) y de los recursos que
 * referencia. Replica paleonorm/config.py: mismas claves, mismos valores por defecto y mismo formato
 * de recursos.
 */
public final class ConfigNormalizacion {

    public String nombre = "sin_nombre";
    public boolean nfkc = true;
    public boolean unirGuiones = true;
    public boolean plegarDiacriticos = true;
    public Map<Integer, String> plegado = new HashMap<>();
    public boolean fechas = false;
    public String numeros = "conservar";
    public boolean fechasGeologicas = false;
    public Map<String, String> multipalabras = new LinkedHashMap<>();
    public Set<String> stopwords = new LinkedHashSet<>();
    public Map<String, String> tesauro = new HashMap<>();
    public String protegidos = "";
    public String raices = "ninguna";
    public Map<String, String> lemas = new HashMap<>();
    public int longitudMinima = 1;
    public int longitudMaxima = 255;

    private static final String SECCION = "normalizacion";

    public static ConfigNormalizacion desdeArchivo(Path rutaConf) throws IOException {
        Map<String, Map<String, String>> ini = leerIni(rutaConf);
        Map<String, String> s = ini.get(SECCION);
        if (s == null) {
            throw new IllegalArgumentException(rutaConf + ": falta la seccion [" + SECCION + "]");
        }
        Path base = rutaConf.toAbsolutePath().getParent();
        ConfigNormalizacion c = new ConfigNormalizacion();
        String nombre = ini.getOrDefault("perfil", Map.of()).get("nombre");
        String archivo = rutaConf.getFileName().toString();
        c.nombre = nombre != null ? nombre : archivo.replaceFirst("\\.[^.]*$", "");
        c.nfkc = booleano(rutaConf, s, "nfkc", true);
        c.unirGuiones = booleano(rutaConf, s, "unir_guiones", true);
        c.plegarDiacriticos = booleano(rutaConf, s, "plegar_diacriticos", true);
        Path plegado = ruta(base, s, "plegado");
        if (plegado != null) {
            for (Map.Entry<String, String> e : cargarMapeo(plegado, ",").entrySet()) {
                if (e.getKey().codePointCount(0, e.getKey().length()) != 1) {
                    throw new IllegalArgumentException(plegado + ": cada forma debe ser un solo caracter: " + e.getKey());
                }
                c.plegado.put(e.getKey().codePointAt(0), e.getValue());
            }
        }
        c.fechas = booleano(rutaConf, s, "fechas", false);
        c.numeros = texto(s, "numeros", "conservar").toLowerCase(Locale.ROOT);
        c.fechasGeologicas = booleano(rutaConf, s, "fechas_geologicas", false);
        Path multi = ruta(base, s, "multipalabras");
        if (multi != null) c.multipalabras = cargarMapeo(multi, "|");
        Path stop = ruta(base, s, "stopwords");
        if (stop != null) c.stopwords = cargarLista(stop);
        Path tesauro = ruta(base, s, "tesauro");
        if (tesauro != null) c.tesauro = cargarMapeo(tesauro, ",");
        c.protegidos = texto(s, "protegidos", "");
        c.raices = texto(s, "raices", "ninguna").toLowerCase(Locale.ROOT);
        Path lemas = ruta(base, s, "lemas");
        if (lemas != null) c.lemas = cargarLemas(lemas);
        c.longitudMinima = Integer.parseInt(texto(s, "longitud_minima", "1"));
        c.longitudMaxima = Integer.parseInt(texto(s, "longitud_maxima", "255"));

        if (!List.of("ninguna", "snowball", "lemas").contains(c.raices)) {
            throw new IllegalArgumentException(rutaConf + ": raices debe ser ninguna, snowball o lemas");
        }
        if (!List.of("conservar", "normalizar").contains(c.numeros)) {
            throw new IllegalArgumentException(rutaConf + ": numeros debe ser conservar o normalizar");
        }
        if (c.raices.equals("lemas") && c.lemas.isEmpty()) {
            throw new IllegalArgumentException(rutaConf + ": raices = lemas requiere un archivo de lemas no vacio");
        }
        return c;
    }

    // ------------------------------------------------------------------ INI

    /** Secciones [x], lineas clave = valor (o clave: valor), comentarios con # o ;. Claves en minusculas. */
    static Map<String, Map<String, String>> leerIni(Path ruta) throws IOException {
        Map<String, Map<String, String>> ini = new LinkedHashMap<>();
        Map<String, String> actual = null;
        int n = 0;
        for (String linea : Files.readAllLines(ruta, StandardCharsets.UTF_8)) {
            n++;
            String l = linea.strip();
            if (l.isEmpty() || l.startsWith("#") || l.startsWith(";")) continue;
            if (l.startsWith("[") && l.endsWith("]")) {
                actual = ini.computeIfAbsent(l.substring(1, l.length() - 1).strip(), k -> new LinkedHashMap<>());
                continue;
            }
            int igual = l.indexOf('='), dosPuntos = l.indexOf(':');
            int corte = igual < 0 ? dosPuntos : (dosPuntos < 0 ? igual : Math.min(igual, dosPuntos));
            if (actual == null || corte < 0) {
                throw new IllegalArgumentException(ruta + ":" + n + ": linea no valida: " + linea);
            }
            actual.put(l.substring(0, corte).strip().toLowerCase(Locale.ROOT), l.substring(corte + 1).strip());
        }
        return ini;
    }

    private static String texto(Map<String, String> s, String clave, String defecto) {
        String v = s.get(clave);
        return v == null || v.isEmpty() ? defecto : v;
    }

    private static boolean booleano(Path conf, Map<String, String> s, String clave, boolean defecto) {
        String v = s.getOrDefault(clave, "").strip().toLowerCase(Locale.ROOT);
        if (v.isEmpty()) return defecto;
        if (!v.equals("si") && !v.equals("no")) {
            throw new IllegalArgumentException(conf + ": " + clave + " debe ser 'si' o 'no', no '" + v + "'");
        }
        return v.equals("si");
    }

    private static Path ruta(Path base, Map<String, String> s, String clave) {
        String v = s.getOrDefault(clave, "").strip();
        return v.isEmpty() ? null : base.resolve(v).normalize();
    }

    // ------------------------------------------------------------------ recursos

    private static List<String> lineasUtiles(Path ruta) throws IOException {
        List<String> out = new ArrayList<>();
        for (String linea : Files.readAllLines(ruta, StandardCharsets.UTF_8)) {
            String l = linea.strip();
            if (!l.isEmpty() && !l.startsWith("#")) out.add(l);
        }
        return out;
    }

    static Set<String> cargarLista(Path ruta) throws IOException {
        return new LinkedHashSet<>(lineasUtiles(ruta));
    }

    /** Lineas 'forma1<sep>forma2 => salida'. La ultima definicion gana. */
    static Map<String, String> cargarMapeo(Path ruta, String separador) throws IOException {
        Map<String, String> mapeo = new LinkedHashMap<>();
        for (String linea : lineasUtiles(ruta)) {
            int flecha = linea.indexOf("=>");
            String salida = flecha < 0 ? "" : linea.substring(flecha + 2).strip();
            if (salida.isEmpty()) {
                throw new IllegalArgumentException(ruta + ": linea sin '=> salida': " + linea);
            }
            for (String forma : linea.substring(0, flecha).split(java.util.regex.Pattern.quote(separador), -1)) {
                forma = forma.strip();
                if (!forma.isEmpty()) mapeo.put(forma, salida);
            }
        }
        return mapeo;
    }

    static Map<String, String> cargarLemas(Path ruta) throws IOException {
        Map<String, String> lemas = new HashMap<>();
        for (String linea : lineasUtiles(ruta)) {
            int tab = linea.indexOf('\t');
            if (tab < 0) continue;
            String lema = linea.substring(tab + 1).strip();
            if (!lema.isEmpty()) lemas.put(linea.substring(0, tab).strip(), lema);
        }
        return lemas;
    }
}
