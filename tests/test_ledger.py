from __future__ import annotations

from pathlib import Path

from rowflow.ledger import build_source_regime_ledger, write_source_regime_ledger


def test_source_regime_ledger_represents_tic_regimes_and_z1(tmp_path: Path) -> None:
    tic = tmp_path / "tic.csv"
    tic.write_text(
        "\n".join(
            [
                "month,quarter,tic_source_regime,tic_treasury_flow_scope,tic_foreign_official_treasury_net_flow_usd_millions,tic_foreign_private_treasury_net_flow_usd_millions",
                "2022-12,2022Q4,legacy_s_form_pre_2023,long_term_treasury_bonds_notes,10,20",
                "2023-02,2023Q1,expanded_slt_2023_on,total_treasuries,30,40",
            ]
        ),
        encoding="utf-8",
    )
    z1 = tmp_path / "z1.csv"
    z1.write_text(
        "\n".join(
            [
                "quarter,z1_foreign_official_treasury_transaction_q_usd_millions,z1_foreign_private_treasury_transaction_q_usd_millions,z1_foreign_total_treasury_transaction_q_usd_millions",
                "2023Q1,5,15,20",
            ]
        ),
        encoding="utf-8",
    )

    ledger = build_source_regime_ledger(tic, z1)
    assert set(ledger["source_family"]) == {
        "tic_legacy_s_form_pre_2023",
        "tic_expanded_slt_2023_on",
        "z1_row_official_private",
    }
    assert ledger["pooling_allowed"].eq(False).all()

    out_csv = tmp_path / "source_regime_ledger.csv"
    out_md = tmp_path / "source_regime_ledger.md"
    written = write_source_regime_ledger(tic, out_csv, z1, out_md)
    assert len(written) == 3
    assert out_csv.exists()
    assert "Source-regime ledger" in out_md.read_text(encoding="utf-8")
