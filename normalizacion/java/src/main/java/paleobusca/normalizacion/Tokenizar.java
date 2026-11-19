package paleobusca.normalizacion;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.TokenStream;
import org.apache.lucene.analysis.tokenattributes.CharTermAttribute;

/**
 * Linea de comandos equivalente a "python -m paleonorm":
 *
 * <pre>
 *   Tokenizar --conf perfiles/p2_stemming.conf [--lineas] &lt; entrada.txt
 * </pre>
 *
 * Con --lineas cada linea es un documento (la secuencia "\n" representa un salto de linea) y se
 * imprime una linea de terminos separados por espacio; sin --lineas se imprime un termino por linea.
 */
public final class Tokenizar {

    public static List<String> terminos(Analyzer analyzer, String texto) throws IOException {
        List<String> out = new ArrayList<>();
        try (TokenStream ts = analyzer.tokenStream("texto", texto)) {
            CharTermAttribute term = ts.addAttribute(CharTermAttribute.class);
            ts.reset();
            while (ts.incrementToken()) out.add(term.toString());
            ts.end();
        }
        return out;
    }

    public static void main(String[] args) throws IOException {
        String conf = null;
        boolean lineas = false;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--conf" -> conf = args[++i];
                case "--lineas" -> lineas = true;
                default -> {
                    System.err.println("argumento desconocido: " + args[i]);
                    System.exit(2);
                }
            }
        }
        if (conf == null) {
            System.err.println("uso: Tokenizar --conf ARCHIVO.conf [--lineas] < entrada");
            System.exit(2);
        }
        try (PaleoAnalyzer analyzer = PaleoAnalyzer.desdeArchivo(Path.of(conf));
             BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
             PrintWriter out = new PrintWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8))) {
            if (lineas) {
                for (String linea; (linea = in.readLine()) != null; ) {
                    out.print(String.join(" ", terminos(analyzer, linea.replace("\\n", "\n"))));
                    out.print('\n');
                }
            } else {
                StringBuilder sb = new StringBuilder();
                char[] buf = new char[8192];
                for (int n; (n = in.read(buf)) != -1; ) sb.append(buf, 0, n);
                out.print(String.join("\n", terminos(analyzer, sb.toString())));
                out.print('\n');
            }
        }
    }
}
