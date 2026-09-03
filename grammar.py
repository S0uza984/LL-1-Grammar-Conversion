from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path


EPSILON = "ε"
EOF = "EOF"


def _common_prefix(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> tuple[str, ...]:
    prefix: list[str] = []
    for left, right in zip(first, second):
        if left != right:
            break
        prefix.append(left)
    return tuple(prefix)


@dataclass(frozen=True)
class Production:
    lhs: str
    rhs: tuple[str, ...]

    def __str__(self) -> str:
        symbols = " ".join(self.rhs) if self.rhs else EPSILON
        return f"{self.lhs} ::= {symbols}"


class Grammar:
    def __init__(self, productions: list[Production]):
        if not productions:
            raise ValueError("a gramática deve possuir ao menos uma produção")

        self.start_symbol = productions[0].lhs
        self.nonterminals = list(
            dict.fromkeys(production.lhs for production in productions)
        )
        self._by_lhs: dict[str, list[Production]] = {
            nonterminal: [] for nonterminal in self.nonterminals
        }
        for production in productions:
            self._by_lhs[production.lhs].append(production)

        self.first: dict[str, set[str]] = {}
        self.follow: dict[str, set[str]] = {}
        self.start: dict[Production, set[str]] = {}

    @property
    def productions(self) -> list[Production]:
        return [
            production
            for nonterminal in self.nonterminals
            for production in self._by_lhs[nonterminal]
        ]

    @property
    def terminals(self) -> set[str]:
        nonterminals = set(self.nonterminals)
        return {
            symbol
            for production in self.productions
            for symbol in production.rhs
            if symbol not in nonterminals
        }

    @classmethod
    def from_text(cls, text: str) -> Grammar:
        productions: list[Production] = []

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "::=" not in line:
                raise ValueError(f"linha {line_number}: esperado '::='")

            lhs, rhs = line.split("::=", 1)
            lhs = lhs.strip()
            if not lhs:
                raise ValueError(f"linha {line_number}: lado esquerdo vazio")

            for alternative in rhs.split("|"):
                alternative = alternative.strip()
                if not alternative:
                    raise ValueError(
                        f"linha {line_number}: alternativa vazia deve usar ε"
                    )
                symbols = tuple(alternative.split())
                if symbols == (EPSILON,):
                    symbols = ()
                elif EPSILON in symbols:
                    raise ValueError(
                        f"linha {line_number}: ε deve ser a alternativa completa"
                    )
                productions.append(Production(lhs, symbols))

        return cls(productions)

    @classmethod
    def from_file(cls, path: str | Path) -> Grammar:
        return cls.from_text(Path(path).read_text(encoding="utf-8"))

    def productions_for(self, nonterminal: str) -> list[Production]:
        return list(self._by_lhs[nonterminal])

    def _empty_sets_by_nonterminal(self) -> dict[str, set[str]]:
        return {nonterminal: set() for nonterminal in self.nonterminals}

    def _invalidate_sets(self) -> None:
        self.first = {}
        self.follow = {}
        self.start = {}

    def _insert_nonterminal_after(self, existing: str, new: str) -> None:
        position = self.nonterminals.index(existing) + 1
        self.nonterminals.insert(position, new)
        self._by_lhs[new] = []

    def _replace_productions(
        self,
        nonterminal: str,
        alternatives: list[tuple[str, ...]],
    ) -> None:
        self._by_lhs[nonterminal] = [
            Production(nonterminal, symbols) for symbols in alternatives
        ]
        self._invalidate_sets()

    def _fresh_nonterminal(self, base: str) -> str:
        candidate = base + "'"
        occupied = set(self.nonterminals) | self.terminals
        while candidate in occupied:
            candidate += "'"
        return candidate

    def first_of_sequence(self, symbols: tuple[str, ...]) -> set[str]:
        """Calcule FIRST para uma sequência de zero ou mais símbolos."""
        resultado = set()
        verificarVazio = True # para verificar se os simbolos podem produzir EPSILON

        for sym in symbols:
            if sym in self.nonterminals:
                first_sym = self.first.get(sym, set()) # pega o first do naoterminal
                resultado.update(first_sym - {EPSILON}) # adicionar o first sem o EPSILON
                if EPSILON not in first_sym: # caso nao produza EPSILON
                    verificarVazio = False 
                    break
            else:  # simbolo terminal
                resultado.add(sym) # adiciona o terminal no first
                verificarVazio = False
                break
        else:
            # se for vazio, adiciona vazio
            if verificarVazio:
                resultado.add(EPSILON)

        return resultado

    def build_first(self) -> None:
        """Preencha self.first por iteração até um ponto fixo."""
        self.first = self._empty_sets_by_nonterminal()
        atualizou = True # condicao para sair do loop, quando nao tiver mudanca FALSE

        while atualizou:
            atualizou = False
            for production in self.productions:
                first_rhs = self.first_of_sequence(production.rhs)
                tamanho = len(self.first[production.lhs]) # guarda o tamanho para ver se ele ira aumentar
                self.first[production.lhs].update(first_rhs) # atualiza o RHS do LHS relacionado
                if len(self.first[production.lhs]) != tamanho:
                    atualizou = True # caso tenha atualizado, repete até obter todos os first

    def build_follow(self) -> None:
        """Preencha self.follow; FIRST deve ter sido calculado antes."""
        if set(self.first) != set(self.nonterminals):
            raise RuntimeError("calcule FIRST antes de FOLLOW")

        self.follow = self._empty_sets_by_nonterminal()
        self.follow[self.start_symbol].add(EOF) # comecando com EOF
        atualizou = True # condicao para sair do loop, quando nao tiver mudanca FALSE

        while atualizou:
            atualizou = False
            for production in self.productions:
                trailer = set(self.follow[production.lhs]) # inicia o trailer com o follow do lado esquerdo

                for symbol in reversed(production.rhs): # para calcular a parte direita, da direita para a esquerda
                    if symbol in self.nonterminals:
                        tamanho = len(self.follow[symbol]) # guarda o tamanho do follow do simbolo para ver se ele ira aumentar
                        self.follow[symbol].update(trailer) # atualiza o follow do simbolo com a informaçao do trailer
                        if len(self.follow[symbol]) != tamanho:
                            atualizou = True

                        symbol_first = self.first[symbol] # verifica o first do simbolo
                        if EPSILON in symbol_first: 
                            trailer = trailer | (symbol_first - {EPSILON}) # quando produz EPSILON, mantem o trailer e adiciona o first do simbolo
                        else:
                            trailer = symbol_first - {EPSILON} # quando nao produz EPSILON, carrega novo trailer sem EPSILON
                    else:
                        trailer = {symbol} # quando terminal, o trailer apaga e recebe somente o simbolo
                        
    def build_start(self) -> None:
        """Associe a cada produção seu conjunto START."""
        if set(self.first) != set(self.nonterminals):
            raise RuntimeError("calcule FIRST antes de START")
        if set(self.follow) != set(self.nonterminals):
            raise RuntimeError("calcule FOLLOW antes de START")

        self.start = {}

        for production in self.productions:
            first_rhs = self.first_of_sequence(production.rhs) # recebe os first da producao gramatical
            if EPSILON in first_rhs:
                start_set = (first_rhs - {EPSILON}) | self.follow[production.lhs] # caso tenha EPSILON no first, adicionar o follow da parte esquerda
            else:
                start_set = first_rhs # senao adiciona somente o first
            self.start[production] = start_set

    def build_sets(self) -> None:
        self.build_first()
        self.build_follow()
        self.build_start()

    def eliminate_direct_left_recursion(self, nonterminal: str) -> bool:
        """Elimine a recursão direta de um não terminal, se existir."""
        productions = self.productions_for(nonterminal)

        # cria duas listas tupla, uma para as entradas recursivas e outra para entradas nao recursivas
        recursivo: list[tuple[str, ...]] = []
        nao_recursivo: list[tuple[str, ...]] = []

        # acumula o alpha e o beta: A -> A alpha | beta
        for prod in productions:
            if prod.rhs and prod.rhs[0] == nonterminal: # verifica se o rhs está vazio e se o primeiro é naoterminal
                recursivo.append(prod.rhs[1:])  # alpha a partir do 1, porque 0 naoterminal
            else:
                nao_recursivo.append(prod.rhs)   # beta

        # nao tem recursao, sai
        if not recursivo:
            return False

        linha = self._fresh_nonterminal(nonterminal) # cria o naoterminal A', se já existir tenta adicionar ' no final
        self._insert_nonterminal_after(nonterminal, linha) # adiciona o A' na gramatica apos o A

        # A -> beta A'
        atualizacao = [beta + (linha,) for beta in nao_recursivo]
        self._replace_productions(nonterminal, atualizacao)

        # A' -> alpha A' | EPSILON
        novaProducao = [alpha + (linha,) for alpha in recursivo]
        novaProducao.append(()) # EPSILON no fim
        self._replace_productions(linha, novaProducao)

        return True

    def eliminate_all_direct_left_recursion(self) -> None:
        for nonterminal in list(self.nonterminals):
            self.eliminate_direct_left_recursion(nonterminal)

    def left_factor_once(self, nonterminal: str) -> bool:
        """Infraestrutura fornecida: fatore um prefixo comum."""
        productions = self.productions_for(nonterminal)
        best_prefix: tuple[str, ...] = ()

        for first, second in combinations(productions, 2):
            prefix = _common_prefix(first.rhs, second.rhs)
            if len(prefix) > len(best_prefix):
                best_prefix = prefix

        if not best_prefix:
            return False

        group = [
            production
            for production in productions
            if production.rhs[: len(best_prefix)] == best_prefix
        ]
        helper = self._fresh_nonterminal(nonterminal)
        self._insert_nonterminal_after(nonterminal, helper)

        alternatives: list[tuple[str, ...]] = []
        inserted = False
        for production in productions:
            if production in group:
                if not inserted:
                    alternatives.append(best_prefix + (helper,))
                    inserted = True
            else:
                alternatives.append(production.rhs)

        suffixes = list(
            dict.fromkeys(
                production.rhs[len(best_prefix) :]
                for production in group
            )
        )
        self._replace_productions(nonterminal, alternatives)
        self._replace_productions(helper, suffixes)
        return True

    def left_factor(self) -> bool:
        """Infraestrutura fornecida: repita a fatoração até estabilizar."""
        changed_any = False
        while True:
            for nonterminal in list(self.nonterminals):
                if self.left_factor_once(nonterminal):
                    changed_any = True
                    break
            else:
                return changed_any

    def ll1_conflicts(
        self,
    ) -> list[tuple[Production, Production, set[str]]]:
        """Infraestrutura fornecida: encontre STARTs sobrepostos."""
        if set(self.start) != set(self.productions):
            raise RuntimeError("calcule START antes de verificar LL(1)")

        conflicts: list[tuple[Production, Production, set[str]]] = []
        for nonterminal in self.nonterminals:
            for first, second in combinations(
                self.productions_for(nonterminal), 2
            ):
                overlap = self.start[first] & self.start[second]
                if overlap:
                    conflicts.append((first, second, overlap))
        return conflicts

    def is_ll1(self) -> bool:
        return not self.ll1_conflicts()

    @staticmethod
    def _format_set(values: set[str]) -> str:
        return "{ " + ", ".join(sorted(values)) + " }"

    def format_sets(self) -> str:
        lines = ["FIRST"]
        lines.extend(
            f"{nonterminal}: {self._format_set(self.first[nonterminal])}"
            for nonterminal in self.nonterminals
        )
        lines.append("")
        lines.append("FOLLOW")
        lines.extend(
            f"{nonterminal}: {self._format_set(self.follow[nonterminal])}"
            for nonterminal in self.nonterminals
        )
        lines.append("")
        lines.append("START")
        lines.extend(
            f"{production}: {self._format_set(self.start[production])}"
            for production in self.productions
        )
        return "\n".join(lines)

    def __str__(self) -> str:
        lines: list[str] = []
        for nonterminal in self.nonterminals:
            alternatives = " | ".join(
                " ".join(production.rhs) if production.rhs else EPSILON
                for production in self.productions_for(nonterminal)
            )
            lines.append(f"{nonterminal} ::= {alternatives}")
        return "\n".join(lines)
