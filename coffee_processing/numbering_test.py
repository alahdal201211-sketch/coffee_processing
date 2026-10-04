import frappe

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
    print("COFFEE NUMBERING - REAL AUTONAME TEST")
    print("=" * 110)

    results = []

    for dt in DOCTYPES:

        print("\n" + "-" * 110)
        print(dt)

        doc1 = None
        doc2 = None

        try:
            meta = frappe.get_meta(dt)

            print("Autoname       :", meta.autoname)
            print("Submittable    :", meta.is_submittable)
            print("Child Table    :", meta.istable)

            doc1 = frappe.get_doc({"doctype": dt})
            doc1.insert(
                ignore_permissions=True,
                ignore_mandatory=True
            )

            name1 = doc1.name

            doc2 = frappe.get_doc({"doctype": dt})
            doc2.insert(
                ignore_permissions=True,
                ignore_mandatory=True
            )

            name2 = doc2.name

            print("TEST 1         :", name1)
            print("TEST 2         :", name2)

            if name1 != name2:
                print("SEQUENCE       : PASS")
                results.append((dt, "PASS", name1, name2))
            else:
                print("SEQUENCE       : FAIL", name1)
                results.append((dt, "FAIL", name1, name2))

        except Exception as e:
            print("STATUS         : ERROR")
            print("ERROR          :", repr(e))
            results.append((dt, "ERROR", repr(e), ""))

        finally:

            for d in (doc2, doc1):

                if d:
                    try:
                        if frappe.db.exists(d.doctype, d.name):

                            frappe.delete_doc(
                                d.doctype,
                                d.name,
                                ignore_permissions=True,
                                force=True
                            )

                    except Exception as e:
                        print("CLEANUP ERROR  :", repr(e))

    frappe.db.commit()

    print("\n" + "=" * 110)
    print("SUMMARY")
    print("=" * 110)

    for dt, status, name1, name2 in results:

        print(
            "{:<30} | {:<10} | {:<25} | {:<25}".format(
                dt,
                status,
                name1,
                name2
            )
        )

    print("=" * 110)
    print("END")
    print("=" * 110)
