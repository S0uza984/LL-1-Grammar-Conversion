from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from grammar import EOF, EPSILON, Grammar  # noqa: E402


def rules(grammar: Grammar, nonterminal: str) -> list[tuple[str, ...]]:
    return [production.rhs for production in grammar.productions_for(nonterminal)]


def test_remove_recursao_direta_com_duas_alternativas():
    grammar = Grammar.from_text(
        """
        Expr ::= Expr PLUS Term | Expr MINUS Term | Term
        Term ::= IDENTIFIER
        """
    )
    assert grammar.eliminate_direct_left_recursion("Expr") is True
    assert rules(grammar, "Expr") == [("Term", "Expr'")]
    assert rules(grammar, "Expr'") == [
        ("PLUS", "Term", "Expr'"),
        ("MINUS", "Term", "Expr'"),
        (),
    ]


def test_first_percorre_sequencias_anulaveis_ate_o_ponto_fixo():
    grammar = Grammar.from_text(
        """
        S ::= A B
        A ::= C | ε
        B ::= b | ε
        C ::= c
        """
    )
    grammar.build_first()
    assert grammar.first["S"] == {"c", "b", EPSILON}
    assert grammar.first["A"] == {"c", EPSILON}
    assert grammar.first_of_sequence(("A", "B")) == {
        "c", "b", EPSILON
    }


def test_follow_propaga_atraves_de_sufixos_anulaveis():
    grammar = Grammar.from_text(
        """
        S ::= A B C
        A ::= a | ε
        B ::= b | ε
        C ::= c | ε
        """
    )
    grammar.build_first()
    grammar.build_follow()
    assert grammar.follow["S"] == {EOF}
    assert grammar.follow["A"] == {"b", "c", EOF}
    assert grammar.follow["B"] == {"c", EOF}
    assert grammar.follow["C"] == {EOF}


def test_start_de_producao_anulavel_inclui_follow():
    grammar = Grammar.from_text(
        """
        S ::= A B
        A ::= a | ε
        B ::= b | ε
        """
    )
    grammar.build_sets()
    terminal_a, empty_a = grammar.productions_for("A")
    terminal_b, empty_b = grammar.productions_for("B")
    assert grammar.start[terminal_a] == {"a"}
    assert grammar.start[empty_a] == {"b", EOF}
    assert grammar.start[terminal_b] == {"b"}
    assert grammar.start[empty_b] == {EOF}


def test_gramatica_microc_comeca_com_conflitos_e_termina_ll1():
    grammar = Grammar.from_file(PROJECT_ROOT / "MicroC.grammar")

    grammar.build_sets()
    assert grammar.ll1_conflicts(), (
        "a gramática inicial deve continuar não LL(1); "
        "não altere MicroC.grammar"
    )

    grammar.eliminate_all_direct_left_recursion()
    assert all(
        not production.rhs or production.rhs[0] != production.lhs
        for production in grammar.productions
    )
    grammar.left_factor()
    grammar.build_sets()

    assert grammar.first["program"] == {
        "KW_INT", "KW_BOOL", "KW_VOID", EPSILON
    }
    assert grammar.follow["expression"] == {
        "COMMA", "RIGHT_PAREN", "SEMICOLON"
    }
    assert grammar.is_ll1()
