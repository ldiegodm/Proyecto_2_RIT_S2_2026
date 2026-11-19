package paleobusca.normalizacion;

import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.util.Map;
import java.util.regex.Pattern;
import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.StopFilter;
import org.apache.lucene.analysis.TokenStream;
import org.apache.lucene.analysis.Tokenizer;
import org.apache.lucene.analysis.miscellaneous.LengthFilter;
import org.apache.lucene.analysis.miscellaneous.PatternKeywordMarkerFilter;
import org.apache.lucene.analysis.miscellaneous.StemmerOverrideFilter;
import org.apache.lucene.analysis.pattern.PatternTokenizer;
import org.apache.lucene.analysis.snowball.SnowballFilter;
import org.tartarus.snowball.ext.EnglishStemmer;

/**
 * Analyzer de Lucene con la normalizacion de PaleoBusca. Cada paso corresponde a uno de
 * ESPECIFICACION.md y a una linea de Normalizador.terminos() en Python:
 *
 * <pre>
 *  1-10  Preprocesador (lee todo el documento y aplica los pasos de texto)   initReader
 *  11    PatternTokenizer          [0-9]+(\.[0-9]+)+[a-z]* | [a-z0-9]+(_[a-z0-9]+)*
 *  12    LengthFilter              longitud_minima .. longitud_maxima
 *  13    StopFilter                stopwords
 *  14    MapeoFilter               tesauro
 *  15    PatternKeywordMarkerFilter protegidos (no se les aplican raices)
 *  16    SnowballFilter(English) | StemmerOverrideFilter(lemas)
 * </pre>
 *
 * Los desplazamientos (offsets) de los terminos se refieren al texto ya preprocesado; el indice
 * de PaleoBusca no los usa.
 */
public final class PaleoAnalyzer extends Analyzer {

    static final Pattern TOKEN = Pattern.compile("[0-9]+(?:\\.[0-9]+)+[a-z]*|[a-z0-9]+(?:_[a-z0-9]+)*");

    private final ConfigNormalizacion config;
    private final Preprocesador preprocesador;
    private final CharArraySet stopwords;
    private final Pattern protegidos;
    private final StemmerOverrideFilter.StemmerOverrideMap lemas;

    public PaleoAnalyzer(ConfigNormalizacion config) {
        this.config = config;
        this.preprocesador = new Preprocesador(config);
        this.stopwords = CharArraySet.unmodifiableSet(new CharArraySet(config.stopwords, false));
        this.protegidos = config.protegidos.isEmpty() ? null : Pattern.compile(config.protegidos);
        try {
            this.lemas = config.raices.equals("lemas") ? construirLemas(config.lemas) : null;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public static PaleoAnalyzer desdeArchivo(Path conf) throws IOException {
        return new PaleoAnalyzer(ConfigNormalizacion.desdeArchivo(conf));
    }

    public ConfigNormalizacion config() {
        return config;
    }

    private static StemmerOverrideFilter.StemmerOverrideMap construirLemas(Map<String, String> lemas) throws IOException {
        StemmerOverrideFilter.Builder b = new StemmerOverrideFilter.Builder(false);
        lemas.forEach(b::add);
        return b.build();
    }

    @Override
    protected Reader initReader(String campo, Reader reader) {
        try {
            StringBuilder sb = new StringBuilder();
            char[] buf = new char[8192];
            for (int n; (n = reader.read(buf)) != -1; ) sb.append(buf, 0, n);
            return new StringReader(preprocesador.preprocesar(sb.toString()));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @Override
    protected TokenStreamComponents createComponents(String campo) {
        Tokenizer fuente = new PatternTokenizer(TOKEN, 0);
        TokenStream ts = new LengthFilter(fuente, config.longitudMinima, config.longitudMaxima);
        if (!stopwords.isEmpty()) ts = new StopFilter(ts, stopwords);
        if (!config.tesauro.isEmpty()) ts = new MapeoFilter(ts, config.tesauro);
        if (!config.raices.equals("ninguna")) {
            if (protegidos != null) ts = new PatternKeywordMarkerFilter(ts, protegidos);
            if (config.raices.equals("snowball")) ts = new SnowballFilter(ts, new EnglishStemmer());
            else ts = new StemmerOverrideFilter(ts, lemas);
        }
        return new TokenStreamComponents(fuente, ts);
    }
}
