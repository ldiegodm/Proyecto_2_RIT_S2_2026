package paleobusca.normalizacion;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

/** Las mismas pruebas golden que python/tests/test_golden.py, ahora con PaleoAnalyzer. */
class GoldenTest {

    static final Path RAIZ = Path.of(System.getProperty("normalizacion.dir", ".."));
    static final Map<String, PaleoAnalyzer> ANALIZADORES = new HashMap<>();

    static PaleoAnalyzer analizador(String perfil) throws IOException {
        PaleoAnalyzer a = ANALIZADORES.get(perfil);
        if (a == null) {
            a = PaleoAnalyzer.desdeArchivo(RAIZ.resolve("perfiles").resolve(perfil + ".conf"));
            ANALIZADORES.put(perfil, a);
        }
        return a;
    }

    static Stream<Arguments> casos() throws IOException {
        List<Arguments> out = new ArrayList<>();
        int n = 0;
        for (String linea : Files.readAllLines(RAIZ.resolve("pruebas/golden.tsv"), StandardCharsets.UTF_8)) {
            n++;
            if (linea.isEmpty() || linea.startsWith("#") || linea.startsWith("perfil\t")) continue;
            String[] c = linea.split("\t", -1);
            out.add(Arguments.of(n, c[0], c[1].replace("\\n", "\n"), c[2]));
        }
        return out.stream();
    }

    @ParameterizedTest(name = "linea {0} - {1}")
    @MethodSource("casos")
    void golden(int linea, String perfil, String entrada, String esperado) throws IOException {
        assertEquals(esperado, String.join(" ", Tokenizar.terminos(analizador(perfil), entrada)));
    }

    @Test
    void versionSnowball() throws IOException {
        // Debe coincidir con snowballstemmer 2.2.0 de Python (ver ESPECIFICACION.md, seccion de versiones).
        assertEquals(List.of("palaeontologist", "ad"),
                Tokenizar.terminos(analizador("p2_stemming"), "palaeontologists added"));
    }

    @Test
    void documentoVacio() throws IOException {
        assertEquals(List.of(), Tokenizar.terminos(analizador("p3_completo"), ""));
    }

    @AfterAll
    static void cerrar() {
        ANALIZADORES.values().forEach(PaleoAnalyzer::close);
    }
}
