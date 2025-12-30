#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import unicodedata
from typing import List, Tuple, Optional, Dict

import pandas as pd
from rapidfuzz import fuzz, process

STOPWORDS = {"da", "de", "do", "das", "dos", "e"}

def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def normalize_name(s: str) -> str:
    if not s or pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = strip_accents(s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = [p for p in s.split() if p not in STOPWORDS]
    return " ".join(parts)

def name_variants(raw: str) -> List[str]:
    variants = set()
    n0 = normalize_name(raw)
    if n0:
        variants.add(n0)

    raw_s = str(raw)
    if "," in raw_s:
        left, right = raw_s.split(",", 1)
        # Tenta o formato "Nome Sobrenome"
        n1 = normalize_name(f"{right.strip()} {left.strip()}")
        if n1:
            variants.add(n1)
    
    return list(variants)

def match_one(
    orientador: str,
    base_norm_names: List[str],
    base_df: pd.DataFrame,
    base_map: Dict[str, int],
    min_score: int = 85,
) -> Tuple[Optional[str], Optional[str], int, str]:
    
    vars_ = name_variants(orientador)

    # 1) Match Exato (Alta Performance com dicionário)
    for v in vars_:
        if v in base_map:
            idx = base_map[v]
            row = base_df.iloc[idx]
            return (
                str(row.get("NameSCOPUS", "")),
                str(row.get("Scopus author ID", "")),
                100,
                "exact",
            )

    # 2) Fuzzy Match (Para variações ortográficas ou nomes incompletos)
    best_score = 0
    best_idx = None
    
    for v in vars_:
        res = process.extractOne(
            v, 
            base_norm_names, 
            scorer=fuzz.token_set_ratio
        )
        if res:
            _, score, idx = res
            if score > best_score:
                best_score = int(score)
                best_idx = idx

    if best_idx is not None and best_score >= min_score:
        row = base_df.iloc[best_idx]
        return (
            str(row.get("NameSCOPUS", "")),
            str(row.get("Scopus author ID", "")),
            best_score,
            "fuzzy",
        )

    return (None, None, int(best_score), "no_match")

def main():
    ap = argparse.ArgumentParser(description="Match de Orientadores UnB com Base Scopus")
    ap.add_argument("--lista", required=True, help="CSV com orientadores e PPG")
    ap.add_argument("--base", required=True, help="CSV base (Todosautoresunb)")
    ap.add_argument("--out", required=True, help="Caminho do CSV de saída")
    ap.add_argument("--min-score", type=int, default=85, help="Score mínimo (0-100)")
    args = ap.parse_args()

    print("Carregando bases...")
    lista_df = pd.read_csv(args.lista)
    base_df = pd.read_csv(args.base)

    col_orientador = "dc.contributor.advisor[pt_BR]"
    col_programa = "dc.description.ppg[pt_BR]"

    # Validação de colunas
    for col in [col_orientador, col_programa]:
        if col not in lista_df.columns:
            raise ValueError(f"Coluna ausente na lista: {col}")
            
    if "NameSCOPUS" not in base_df.columns:
        raise ValueError("A base precisa da coluna 'NameSCOPUS'")

    print("Normalizando base de autores (isso pode levar alguns segundos)...")
    # Criamos a lista normalizada e o mapa de busca exata
    base_norm = [normalize_name(n) for n in base_df["NameSCOPUS"].fillna("")]
    base_map = {name: i for i, name in enumerate(base_norm) if name}

    # Pegamos apenas orientadores únicos para não repetir trabalho
    orientadores_unicos = lista_df[[col_orientador, col_programa]].drop_duplicates()
    
    print(f"Processando {len(orientadores_unicos)} orientadores únicos...")
    
    results = []
    for _, row_l in orientadores_unicos.iterrows():
        orig_name = str(row_l[col_orientador])
        ppg = str(row_l[col_programa])
        
        nomescopus, scopus_id, score, method = match_one(
            orig_name, base_norm, base_df, base_map, args.min_score
        )
        
        results.append({
            "orientador_original": orig_name,
            "programa_ppg": ppg,
            "NameSCOPUS": nomescopus,
            "Scopus author ID": scopus_id,
            "match_score": score,
            "match_method": method
        })

    out_df = pd.DataFrame(results)
    out_df.to_csv(args.out, index=False, encoding="utf-8-sig")
    
    # Resumo para o GID
    exact_count = len(out_df[out_df["match_method"] == "exact"])
    fuzzy_count = len(out_df[out_df["match_method"] == "fuzzy"])
    print(f"\nConcluído!")
    print(f"Total processado: {len(out_df)}")
    print(f"Matches exatos: {exact_count}")
    print(f"Matches fuzzy: {fuzzy_count}")
    print(f"Arquivo salvo em: {args.out}")

if __name__ == "__main__":
    main()