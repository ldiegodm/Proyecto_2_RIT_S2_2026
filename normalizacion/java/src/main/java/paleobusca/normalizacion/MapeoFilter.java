package paleobusca.normalizacion;

import java.io.IOException;
import java.util.Map;
import org.apache.lucene.analysis.TokenFilter;
import org.apache.lucene.analysis.TokenStream;
import org.apache.lucene.analysis.tokenattributes.CharTermAttribute;

/**
 * Paso 14 (tesauro): reemplaza un termino por su forma canonica, un token por un token.
 * No marca el termino como palabra clave, de modo que despues todavia se le aplican las raices
 * (a diferencia de StemmerOverrideFilter, que si lo marca).
 */
public final class MapeoFilter extends TokenFilter {

    private final Map<String, String> mapeo;
    private final CharTermAttribute term = addAttribute(CharTermAttribute.class);

    public MapeoFilter(TokenStream entrada, Map<String, String> mapeo) {
        super(entrada);
        this.mapeo = mapeo;
    }

    @Override
    public boolean incrementToken() throws IOException {
        if (!input.incrementToken()) return false;
        String nuevo = mapeo.get(term.toString());
        if (nuevo != null) term.setEmpty().append(nuevo);
        return true;
    }
}
