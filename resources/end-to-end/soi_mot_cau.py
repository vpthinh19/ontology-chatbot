"""Hỏi lại đúng một câu và in cả dữ liệu công cụ trả về, để đối chiếu tay."""
import asyncio, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import chay
from ontchatbot.runtime.model import CTranslate2Generator

async def main():
    cau = sys.argv[1]
    gen = CTranslate2Generator.load(Path("artifacts/ct2/t5gemma2"), device="cpu", compute_type="int8")
    from ontchatbot.runtime.agent import build_agent
    agent = build_agent(chay.ChatbotCoVet(gen), model=os.environ["ONTCHATBOT_LLM_MODEL"])
    vet = {"goi": [], "du_lieu": []}
    chay.luot.set(vet)
    from agents import Runner
    ket = await Runner.run(agent, cau, max_turns=12)
    print("TỪ KHOÁ:", [k for g in vet["goi"] for k in g["tu_khoa"]])
    print("NODE   :", sorted({n for g in vet["goi"] for n in g["node"]}))
    du = "\n".join(vet["du_lieu"])
    for tu in ("GDTC", "GDQP", "5.5", "5,5"):
        print(f"  '{tu}' có trong dữ liệu công cụ:", tu in du)
    print("\nTRẢ LỜI:\n", (ket.final_output or "")[:400])

asyncio.run(main())
