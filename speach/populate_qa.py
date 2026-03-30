
from database import get_db_connection


def insert_local_knowledge(content, source="Manual"):

    conn = get_db_connection()

    cur = conn.cursor()

    

    query = """

    INSERT INTO local_context (content, source, confidence, product_relevance)

    VALUES (%s, %s, %s, %s)

    """

    

    # We set confidence to 1.0 so your QA module knows this is the absolute truth!

    cur.execute(query, (content, source, 1.0, "General"))

    

    conn.commit()

    cur.close()

    conn.close()

    print("הנתונים הוזנו בהצלחה למסד הנתונים!")


# --- PASTE YOUR LOCAL TEXT HERE ---

my_data = """

המדפסת המשרדית נמצאת בקומה 2 בחדר 204. קוד הגישה למכונת הצילום הוא 1234.

שעות הפעילות של המשרד הן בימים א'-ה' בין השעות 08:00 ל-17:00.

"""


insert_local_knowledge(my_data, source="Office Guide")

