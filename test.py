from src.ontchatbot.core.pipeline import extract_entities

text1 = "dkhp như nào nhỉ, mức hc phí k65 cntt thì sao"
text2 = "hc phí k65 vs k67 như nào"
text3 = "tui rớt môn r, hc lại như nào z"
text4 = "điểm thấp quá, làm sao giờ"
entities1 = extract_entities(text1)
entities2 = extract_entities(text2)
entities3 = extract_entities(text3)
entities4 = extract_entities(text4)
print(entities1)
print(entities2)
print(entities3)
print(entities4)