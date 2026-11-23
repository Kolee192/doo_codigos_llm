import com.sun.source.tree.*;
import com.sun.source.util.*;
import javax.lang.model.element.Modifier;
import javax.tools.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

/** Calcula NOM, NPM, NATTR e LCOM (Henderson-Sellers) por tipo declarado, so com analise sintatica. */
public class Metricas {
    static PrintWriter out;
    static String modelo, esp, arquivo;
    static int errosParse;
    static SourcePositions pos;
    static CompilationUnitTree cu;

    public static void main(String[] a) throws Exception {
        Path raiz = Paths.get(a[0]);
        out = new PrintWriter(Files.newBufferedWriter(Paths.get(a[1])));
        out.println("modelo,esp,arquivo,classe,tipo,nom,npm,ncons,nattr,metodos_lcom,lcom_hs,linhas,erros_parse_arquivo");
        JavaCompiler comp = ToolProvider.getSystemJavaCompiler();
        List<Path> arqs;
        try (Stream<Path> s = Files.walk(raiz)) { arqs = s.filter(p -> p.toString().endsWith(".java")).sorted().collect(Collectors.toList()); }
        for (Path p : arqs) {
            Path rel = raiz.relativize(p);
            modelo = rel.getName(0).toString(); esp = rel.getName(1).toString(); arquivo = p.getFileName().toString();
            DiagnosticCollector<JavaFileObject> diag = new DiagnosticCollector<>();
            try (StandardJavaFileManager fm = comp.getStandardFileManager(diag, null, java.nio.charset.StandardCharsets.UTF_8)) {
                JavacTask task = (JavacTask) comp.getTask(null, fm, diag, List.of("-proc:none"), null, fm.getJavaFileObjects(p.toFile()));
                Iterable<? extends CompilationUnitTree> units = task.parse();
                pos = Trees.instance(task).getSourcePositions();
                errosParse = (int) diag.getDiagnostics().stream().filter(d -> d.getKind() == Diagnostic.Kind.ERROR).count();
                for (CompilationUnitTree u : units) {
                    cu = u;
                    for (Tree t : u.getTypeDecls()) if (t instanceof ClassTree) tipo((ClassTree) t, "");
                }
            }
        }
        out.close();
    }

    static boolean ehMetodoInterface(ClassTree c) { return c.getKind() == Tree.Kind.INTERFACE || c.getKind() == Tree.Kind.ANNOTATION_TYPE; }

    static void tipo(ClassTree c, String prefixo) {
        String nome = c.getSimpleName().toString();
        if (nome.isEmpty()) return; // classe anonima: nao e uma unidade
        String qual = prefixo.isEmpty() ? nome : prefixo + "." + nome;
        boolean iface = ehMetodoInterface(c);
        List<MethodTree> metodos = new ArrayList<>();
        int ncons = 0;
        List<String> atributos = new ArrayList<>();
        List<ClassTree> aninhadas = new ArrayList<>();
        for (Tree m : c.getMembers()) {
            if (m instanceof MethodTree) {
                MethodTree mt = (MethodTree) m;
                if (mt.getName().contentEquals("<init>")) { ncons++; } else metodos.add(mt);
            } else if (m instanceof VariableTree) {
                VariableTree v = (VariableTree) m;
                Set<Modifier> mods = v.getModifiers().getFlags();
                boolean constanteEnum = false; // constantes de enum sao static e ja saem pelo filtro de static
                if (!iface && !mods.contains(Modifier.STATIC) && !constanteEnum) atributos.add(v.getName().toString());
            } else if (m instanceof ClassTree) aninhadas.add((ClassTree) m);
        }
        int nom = metodos.size(), npm = 0;
        for (MethodTree mt : metodos) {
            Set<Modifier> f = mt.getModifiers().getFlags();
            if (f.contains(Modifier.PUBLIC) || (iface && !f.contains(Modifier.PRIVATE))) npm++;
        }
        // LCOM-HS: metodos de instancia com corpo
        List<MethodTree> inst = metodos.stream().filter(mt -> mt.getBody() != null && !mt.getModifiers().getFlags().contains(Modifier.STATIC)).collect(Collectors.toList());
        int m = inst.size(), a = atributos.size();
        String lcom = "";
        if (m > 1 && a > 0) {
            int soma = 0;
            Map<MethodTree, Set<String>> usos = new HashMap<>();
            for (MethodTree mt : inst) usos.put(mt, camposUsados(mt, new HashSet<>(atributos)));
            for (String at : atributos) soma += (int) inst.stream().filter(mt -> usos.get(mt).contains(at)).count();
            lcom = String.format(Locale.ROOT, "%.4f", (m - (double) soma / a) / (m - 1));
        }
        long ini = pos.getStartPosition(cu, c), fim = pos.getEndPosition(cu, c);
        int linhas = 0;
        if (ini >= 0 && fim >= 0) linhas = (int) (cu.getLineMap().getLineNumber(fim) - cu.getLineMap().getLineNumber(ini) + 1);
        out.printf("%s,%s,%s,%s,%s,%d,%d,%d,%d,%d,%s,%d,%d%n", modelo, esp, arquivo, qual, c.getKind(), nom, npm, ncons, a, m, lcom, linhas, errosParse);
        for (ClassTree n : aninhadas) tipo(n, qual);
        // tipos locais declarados dentro de metodos
        for (MethodTree mt : metodos) if (mt.getBody() != null) new TreeScanner<Void, Void>() {
            @Override public Void visitClass(ClassTree t, Void v) { tipo(t, qual); return null; }
        }.scan(mt.getBody(), null);
    }

    /** Campos (da lista) referenciados no metodo, por nome simples (nao sombreado) ou por this.nome. */
    static Set<String> camposUsados(MethodTree mt, Set<String> campos) {
        Set<String> locais = new HashSet<>();
        for (VariableTree p : mt.getParameters()) locais.add(p.getName().toString());
        new TreeScanner<Void, Void>() {
            @Override public Void visitVariable(VariableTree v, Void x) { locais.add(v.getName().toString()); return super.visitVariable(v, x); }
        }.scan(mt.getBody(), null);
        Set<String> usados = new HashSet<>();
        new TreeScanner<Void, Void>() {
            @Override public Void visitIdentifier(IdentifierTree id, Void x) {
                String n = id.getName().toString();
                if (campos.contains(n) && !locais.contains(n)) usados.add(n);
                return null;
            }
            @Override public Void visitMemberSelect(MemberSelectTree ms, Void x) {
                if (ms.getExpression() instanceof IdentifierTree && ((IdentifierTree) ms.getExpression()).getName().contentEquals("this")) {
                    String n = ms.getIdentifier().toString();
                    if (campos.contains(n)) usados.add(n);
                    return null;
                }
                return scan(ms.getExpression(), x);
            }
            @Override public Void visitMethodInvocation(MethodInvocationTree mi, Void x) {
                ExpressionTree sel = mi.getMethodSelect();
                if (sel instanceof MemberSelectTree) scan(((MemberSelectTree) sel).getExpression(), x); // so o alvo; o nome do metodo nao e campo
                scan(mi.getArguments(), x);
                return null;
            }
        }.scan(mt.getBody(), null);
        return usados;
    }
}
