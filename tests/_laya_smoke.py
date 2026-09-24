
import time
t0 = time.time()
import laya
agent = laya.load("convaiinnovations/laya")
print("LOAD_S", round(time.time()-t0, 1))
t1 = time.time()
result = agent.predict(
    "set the format to mp4",
    {"difficulty": {"type": "choice", "instructions": "How complex is this request?",
                    "criteria": ["EASY","MEDIUM","HARD","EXPERT"]}},
)
print("PREDICT_S", round(time.time()-t1, 3))
print("RESULT", result)
