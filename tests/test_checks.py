import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.agents.checks import (looks_like_date, looks_like_money, type_problem,
                               evidence_for, labelled_evidence, snap_to_line)

STACKED = "Invoice Number\nINV-4410\nPayment Due Date\nMay 22, 2026\nSubtotal\n$640.00"
SINGLE = "Invoice Date: Feb 9, 2026\nTerms: Net 30\nBalance Due: $929.34\nDue on: 2026-05-02"


def test_date_formats():
    for d in ["March 3, 2026", "14 March 2026", "2026-04-02", "07/15/2026", "Feb 9, 2026"]:
        assert looks_like_date(d), d
    assert not looks_like_date("$929.34")
    assert not looks_like_date("Payment Due Date")


def test_money_formats():
    for m in ["$7,350.00", "4200.00", "USD 1,980.00", "$99.36"]:
        assert looks_like_money(m), m
    assert not looks_like_money("Subtotal")


def test_a_label_is_not_a_valid_value():
    assert type_problem("invoice_number", "Invoice Number") == "no_digits"
    assert type_problem("vendor_name", "Vendor") == "is_a_label"
    assert type_problem("subtotal", "Tax") == "not_an_amount"
    assert type_problem("vendor_name", "Crescent Foods Pvt Ltd") is None


def test_an_amount_is_not_a_date():
    assert type_problem("due_date", "$929.34") == "not_a_date"


def test_invoice_date_cannot_be_verified_as_a_due_date():
    assert labelled_evidence("due_date", evidence_for("Feb 9, 2026", SINGLE)) == []


def test_real_due_date_line_is_accepted():
    assert labelled_evidence("due_date", evidence_for("2026-05-02", SINGLE)) == ["Due on: 2026-05-02"]


def test_label_on_the_previous_line_counts_in_a_two_column_layout():
    evidence = evidence_for("INV-4410", STACKED)
    assert evidence == ["Invoice Number INV-4410"]
    assert labelled_evidence("invoice_number", evidence) == evidence


def test_subtotal_cannot_be_verified_as_total():
    assert labelled_evidence("total", evidence_for("$640.00", STACKED)) == []


def test_truncated_answers_are_extended_to_the_end_of_the_line():
    assert snap_to_line("Crescent Foods", "From: Crescent Foods Pvt Ltd") == "Crescent Foods Pvt Ltd"
    assert snap_to_line("Delta Courier", "Delta Courier Services") == "Delta Courier Services"


def test_a_label_is_not_extended_into_the_value():
    assert snap_to_line("Total Amount Due", "Total Amount Due: $4536.00") == "Total Amount Due"
