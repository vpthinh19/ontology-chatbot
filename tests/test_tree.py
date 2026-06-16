"""tree.parse: validate cấu trúc cây JSON + bỏ node ma (§3/§8)."""

from __future__ import annotations

from ontchatbot.tree import DATA, INDIVIDUAL, QUERY, VAGUE, parse


def test_parse_query_nested():
    c = parse({"act": "query", "entities": [
        {"label": "học phí", "type": "individual", "children": [
            {"label": "k65", "type": "individual", "children": []}]}]})
    assert c.act == QUERY
    assert c.root.label == "học phí" and c.root.kind == INDIVIDUAL
    assert c.root.children[0].label == "k65"


def test_acts_without_tree():
    assert parse({"act": "greeting", "entities": []}).root is None
    assert parse({"act": "ood"}).act == "ood"
    assert parse({"act": "vague"}).act == VAGUE


def test_bad_act_to_vague():
    assert parse({"act": "chitchat", "entities": []}).act == VAGUE


def test_non_dict_to_vague():
    assert parse("nope").act == VAGUE
    assert parse(None).act == VAGUE


def test_empty_entities_to_vague():
    assert parse({"act": "query", "entities": []}).act == VAGUE


def test_root_must_be_individual():
    bad = {"act": "query", "entities": [{"label": "x", "type": "object", "children": []}]}
    assert parse(bad).act == VAGUE


def test_ghost_children_dropped():
    c = parse({"act": "query", "entities": [{"label": "a", "type": "individual", "children": [
        {"label": "", "type": "object"},          # label rỗng
        {"type": "data"},                          # thiếu label
        {"label": "x", "type": "banana"},          # loại sai
        {"label": "ok", "type": "object", "children": []}]}]})
    assert [n.label for n in c.root.children] == ["ok"]


def test_data_node_strips_children():
    c = parse({"act": "query", "entities": [{"label": "a", "type": "individual", "children": [
        {"label": "email", "type": "data", "children": [
            {"label": "x", "type": "data", "children": []}]}]}]})
    leaf = c.root.children[0]
    assert leaf.kind == DATA and leaf.children == ()
