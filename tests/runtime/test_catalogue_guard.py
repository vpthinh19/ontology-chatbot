from types import SimpleNamespace

from ontchatbot.catalogue import find_query_family, load_catalogue
from ontchatbot.runtime.pipeline import OntologyChatbot
from ontchatbot.runtime.render import NO_INFORMATION_REPLY
from ontchatbot.settings import QUERY_CATALOGUE_PATH

def _procedure_target() -> str:
    """Đích chuẩn của ``academic-procedure-facts``, lấy thẳng từ danh mục.

    KHÔNG chốt cứng chuỗi truy vấn: khuôn dump đổi vài lần trong lúc dựng lại
    danh mục, và mỗi lần đổi là phép kiểm mục theo dù hợp đồng không hề đổi.
    Thứ cần canh là "đích của một họ có khớp danh mục không", không phải mặt chữ.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    return catalogue["academic-procedure-facts"].target_template.replace(
        "${anchor}", ":TemporaryAcademicLeaveProcedure"
    )


SUBMISSION_OFFICE = _procedure_target()
# Valid SPARQL, real entities, but no declared family combines them. Left
# unchecked it dumps every article of the regulation into the reply.
UNBOUND_ARTICLE_DUMP = (
    "SELECT ?answer WHERE { ?item a :AcademicProcedure ; :hasStep ?part . "
    "?part :stepText ?answer . }"
)


def test_find_query_family_accepts_a_canonical_target() -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    assert find_query_family(catalogue, SUBMISSION_OFFICE) == "academic-procedure-facts"


def test_find_query_family_rejects_an_undeclared_combination() -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    assert find_query_family(catalogue, UNBOUND_ARTICLE_DUMP) is None


def test_chatbot_answers_a_query_that_matches_a_declared_family() -> None:
    generator = SimpleNamespace(generate=lambda _: SUBMISSION_OFFICE)

    reply = OntologyChatbot(generator).answer("bảo lưu nộp ở đâu")

    assert "Phòng Công tác Chính trị và Sinh viên" in reply


def test_chatbot_refuses_a_query_outside_the_catalogue() -> None:
    generator = SimpleNamespace(generate=lambda _: UNBOUND_ARTICLE_DUMP)

    reply = OntologyChatbot(generator).answer("liên thông thế nào")

    assert reply == NO_INFORMATION_REPLY


def test_empty_catalogue_disables_the_conformance_check() -> None:
    generator = SimpleNamespace(generate=lambda _: UNBOUND_ARTICLE_DUMP)

    reply = OntologyChatbot(generator, catalogue={}).answer("liên thông thế nào")

    assert reply != NO_INFORMATION_REPLY


def test_off_catalogue_rejection_is_logged(caplog) -> None:
    generator = SimpleNamespace(generate=lambda _: UNBOUND_ARTICLE_DUMP)

    with caplog.at_level("INFO", logger="ontchatbot.runtime.pipeline"):
        OntologyChatbot(generator).answer("liên thông thế nào")

    assert "off-catalogue query rejected" in "\n".join(
        record.getMessage() for record in caplog.records
    )
