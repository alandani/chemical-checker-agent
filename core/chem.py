"""Small RDKit helpers: parsing, identifiers, drawing."""

from __future__ import annotations

import io

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Descriptors, Draw, rdMolDescriptors

RDLogger.DisableLog("rdApp.*")


def mol_from_smiles(smiles: str) -> Chem.Mol | None:
    if not smiles or " " in smiles.strip():
        return None
    return Chem.MolFromSmiles(smiles.strip())


def strip_atom_maps(smiles: str) -> str:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return smiles
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(mol)


def canonical(smiles: str) -> str | None:
    mol = mol_from_smiles(smiles)
    return Chem.MolToSmiles(mol) if mol else None


def inchikey(smiles: str) -> str | None:
    mol = mol_from_smiles(smiles)
    return Chem.MolToInchiKey(mol) if mol else None


def describe(smiles: str) -> dict | None:
    """Identifiers and basic properties computed locally (no network)."""
    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    return {
        "smiles": Chem.MolToSmiles(mol),
        "inchikey": Chem.MolToInchiKey(mol),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "mol_weight": round(Descriptors.MolWt(mol), 3),
    }


def mol_weight(smiles: str) -> float | None:
    mol = mol_from_smiles(smiles)
    return Descriptors.MolWt(mol) if mol else None


def mol_png(smiles: str, size: tuple[int, int] = (300, 220)) -> bytes | None:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    img = Draw.MolToImage(mol, size=size)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def reaction_png(reaction_smiles: str, size: tuple[int, int] = (700, 200)) -> bytes | None:
    try:
        rxn = AllChem.ReactionFromSmarts(reaction_smiles, useSmiles=True)
        img = Draw.ReactionToImage(rxn, subImgSize=(size[0] // 4, size[1]))
    except Exception:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
