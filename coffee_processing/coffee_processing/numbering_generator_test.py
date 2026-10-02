import frappe
from frappe.model.naming import make_autoname

DOCTYPES = [
    "Coffee Receiving Order",
    "Coffee Sorting Order",
    "Coffee Fermentation Order",
    "Coffee Drying Order",
    "Coffee Peeling Service",
    "Coffee Grading Order",
    "Coffee Cupping",
    "Coffee Blend Order",
    "Coffee Packaging Order",
    "Coffee Process Order",
    "Coffee Process Trial",
    "Coffee Production Plan",
    "Coffee Batch",
]


def run():
    print("=" * 110)
    print("COFFEE NUMBERING - AUTONAME GENERATOR TEST")
    print("=" * 110)

    for dt in DOCTYPES:

        meta = frappe.get_meta(dt)

        print("\n" + "-" * 110)
        print(dt)
        print("AUTONAME :", meta.autoname)

        try:
            name1 = make_autoname(meta.autoname)
            name2 = make_autoname(meta.autoname)

            print("GENERATED 1 :", name1)
            print("GENERATED 2 :", name2)

            if name1 != name2:
                print("RESULT      : PASS")
            else:
                print("RESULT      : CHECK")

        except Exception as e:
            print("RESULT      : ERROR")
            print("ERROR       :", repr(e))

    print("\n" + "=" * 110)
    print("END")
    print("=" * 110)
