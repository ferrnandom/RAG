import requests

while True:
    query = str(input("Please ask any question: "))
    response = requests.post(
        "http://127.0.0.1:8000/answer",
        json={"query": query},
    )
    answer = response.json()
    print(answer["answer"])
    for src in answer["sources"]:
        print(f"[{src['citation']}] {src['source']} (pages {src['page_numbers']})")
