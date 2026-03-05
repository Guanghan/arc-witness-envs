import requests, json

# Fetch all puzzles from The Windmill and store in all_puzzles.json

response = requests.get("https://windmill.thefifthmatt.com/_/things")
data = json.loads(response.content)

all_data = []

all_data.extend(data["things"])

while data["hasMore"]:
  last_id = all_data[-1]["id"]
  print "fetching from %s" % last_id
  response = requests.get("https://windmill.thefifthmatt.com/_/things?start=%s" % last_id)
  data = json.loads(response.content)
  all_data.extend(data["things"])


f = open("all_puzzles.json", "w")
f.write(json.dumps(all_data))
f.close()