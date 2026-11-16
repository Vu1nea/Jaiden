"""Build web/mock/recipes.json: hand-written recipes tagged with real ingredient labels.

Usage: python scripts/build_mock_recipes.py ingredient_categorization/labeled_manual_combined.csv web/mock/recipes.json

A flag is set if <flag>==1 or maybe_<flag>==1 in any case variant of the ingredient
name; an ingredient is unknown if missing from the CSV or any variant is marked unclear.
"""
import csv, json, sys
F = ["tree_nut","peanut","dairy","gluten","egg","soy","fish","shellfish","sesame","meat","pork","beef","protein_source"]
# Union labels across case variants ("oats" vs "Oats" can carry different flags).
labels = {}
for x in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    key = x["ingredient"].strip().lower()
    cur = labels.setdefault(key, {"flags": set(), "unclear": False})
    cur["flags"].update(f for f in F if x[f] == "1" or x.get("maybe_" + f) == "1")
    cur["unclear"] = cur["unclear"] or x["unclear"] == "1"

R = [
 ("Spicy Ground Beef Skillet", "www.cookbooks.com/Recipe-Details.aspx?id=1042", "Gathered",
  [("1 lb. ground beef","ground beef"),("1 onion, chopped","onion"),("2 cloves garlic","garlic"),("1 Tbsp. chili powder","chili powder"),("1 tsp. cumin","cumin"),("1 jalapeno, minced","jalapeno"),("1 can tomatoes","tomatoes"),("1 c. cheddar cheese","cheddar cheese"),("2 c. cooked rice","rice")]),
 ("Dim Sum Pork and Ginger Dumplings", "https://www.allrecipes.com/recipe/14759/pork-dumplings/", "Recipes1M",
  [("1/2 lb. ground pork","ground pork"),("2 Tbsp. soy sauce","soy sauce"),("1 Tbsp. ginger, grated","ginger"),("3 green onions","green onions"),("1 pkg. wonton wrappers","wonton wrappers"),("1 tsp. sesame oil","sesame oil")]),
 ("Crispy Fried Dim Sum Dumplings", "https://www.food.com/recipe/crispy-fried-dumplings-88231", "Gathered",
  [("1/2 lb. ground pork","ground pork"),("1 pkg. wonton wrappers","wonton wrappers"),("2 Tbsp. soy sauce","soy sauce"),("1/4 c. peanut oil for frying","peanut oil"),("2 green onions","green onions")]),
 ("Shrimp Har Gow (Dim Sum)", "https://www.epicurious.com/recipes/food/views/har-gow", "Recipes1M",
  [("1/2 lb. shrimp, minced","shrimp"),("1 Tbsp. cornstarch","cornstarch"),("1 tsp. sesame oil","sesame oil"),("1 c. wheat starch dough","flour"),("hot water","water")]),
 ("Creamy Parmesan Pasta", "www.cookbooks.com/Recipe-Details.aspx?id=2290", "Gathered",
  [("1 lb. pasta","pasta"),("1 c. heavy cream","heavy cream"),("4 Tbsp. butter","butter"),("1 c. parmesan cheese","parmesan cheese"),("2 cloves garlic","garlic"),("salt","salt"),("pepper","pepper")]),
 ("High-Protein Lemon Chicken Quinoa Dinner", "https://www.food.com/recipe/lemon-chicken-quinoa-401122", "Recipes1M",
  [("2 chicken breasts","chicken breast"),("1 c. quinoa","quinoa"),("2 Tbsp. olive oil","olive oil"),("1 lemon, juiced","lemon"),("2 c. broccoli","broccoli"),("1 can black beans","black beans")]),
 ("Za'atar Flatbread", "https://www.food52.com/recipes/zaatar-flatbread", "Recipes1M",
  [("2 pita breads","pita"),("2 Tbsp. zaatar","zaatar"),("3 Tbsp. olive oil","olive oil"),("1/2 c. yogurt","yogurt"),("1 cucumber","cucumber")]),
 ("Fresh Tomato Salsa", "www.cookbooks.com/Recipe-Details.aspx?id=377", "Gathered",
  [("4 tomatoes, diced","tomatoes"),("1/2 onion","onion"),("1 jalapeno","jalapeno"),("1/4 c. fresh cilantro","cilantro"),("1 lime, juiced","lime"),("salt","salt")]),
 ("Honey Dill Salmon", "https://www.allrecipes.com/recipe/22841/honey-dill-salmon/", "Recipes1M",
  [("2 salmon fillets","salmon"),("2 Tbsp. honey","honey"),("1 Tbsp. fresh dill","dill"),("1 lemon","lemon"),("1 Tbsp. olive oil","olive oil")]),
 ("Almond Oat Breakfast Bars", "", "Gathered",
  [("2 c. oats","oats"),("1/2 c. almonds","almonds"),("1/3 c. honey","honey"),("1 egg","egg"),("1 tsp. vanilla","vanilla"),("1 tsp. cinnamon","cinnamon")]),
 ("Peanut Tofu Noodles", "https://www.food.com/recipe/peanut-tofu-noodles-312904", "Recipes1M",
  [("8 oz. noodles","noodles"),("1 block tofu","tofu"),("1/4 c. peanuts, crushed","peanuts"),("3 Tbsp. soy sauce","soy sauce"),("2 c. bok choy","bok choy"),("1 Tbsp. sesame oil","sesame oil")]),
 ("Coconut Lentil Curry", "https://www.epicurious.com/recipes/food/views/coconut-lentil-curry", "Recipes1M",
  [("1 c. lentils","lentils"),("1 can coconut milk","coconut milk"),("2 Tbsp. curry paste","curry paste"),("2 carrots","carrots"),("1 onion","onion"),("2 c. spinach","spinach")]),
 ("Turkey Meatballs", "www.cookbooks.com/Recipe-Details.aspx?id=5120", "Gathered",
  [("1 lb. ground turkey","turkey"),("1/2 c. bread crumbs","bread crumbs"),("1 egg","egg"),("1/2 c. parmesan cheese","parmesan cheese"),("2 cloves garlic","garlic")]),
 ("Baked Pork Chops with Apples", "https://www.allrecipes.com/recipe/14596/baked-pork-chops/", "Recipes1M",
  [("4 pork chops","pork chops"),("2 apples, sliced","apples"),("2 Tbsp. maple syrup","maple syrup"),("1 tsp. cinnamon","cinnamon"),("1 tsp. thyme","thyme")]),
 ("Vegetable Barley Soup", "www.cookbooks.com/Recipe-Details.aspx?id=8811", "Gathered",
  [("6 c. vegetable broth","vegetable broth"),("2 carrots","carrots"),("2 stalks celery","celery"),("1 onion","onion"),("2 potatoes","potatoes"),("1 c. mushrooms","mushrooms")]),
 ("Spinach Feta Omelet", "https://www.food.com/recipe/spinach-feta-omelet-77310", "Recipes1M",
  [("3 eggs","egg"),("1 c. spinach","spinach"),("1/4 c. feta cheese","feta cheese"),("1 Tbsp. butter","butter"),("pepper","pepper")]),
]
out = []
for i, (title, link, source, ings) in enumerate(R, 1):
    items, rflags = [], {}
    for raw, name in ings:
        x = labels.get(name)
        if x is None:
            items.append({"raw": raw, "name": name, "flags": [], "known": False}); continue
        fl = [f for f in F if f in x["flags"]]
        for f in fl: rflags[f] = 1
        items.append({"raw": raw, "name": name, "flags": fl, "known": not x["unclear"]})
    out.append({"id": i, "title": title, "link": link, "source": source, "ingredients": items, "flags": rflags})
json.dump(out, open(sys.argv[2], "w", encoding="utf-8", newline="\n"), indent=2)
print(len(out))
