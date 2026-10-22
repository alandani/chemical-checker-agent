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


_INK_LIGHT = (0.075, 0.13, 0.17)  # matches the UI ink colour
_INK_DARK = (0.86, 0.9, 0.93)


def _svg_options(drawer, theme: str) -> None:
    from rdkit.Chem.Draw import rdMolDraw2D

    opts = drawer.drawOptions()
    if theme == "dark":
        rdMolDraw2D.SetDarkMode(opts)
        opts.updateAtomPalette({-1: _INK_DARK, 6: _INK_DARK})
    else:
        opts.updateAtomPalette({-1: _INK_LIGHT, 6: _INK_LIGHT})
    opts.clearBackground = False
    opts.bondLineWidth = 1.6
    opts.padding = 0.08
    opts.additionalAtomLabelPadding = 0.12


def _clean_svg(svg: str) -> str:
    # Drop the XML prolog so the SVG can be inlined or served as-is.
    return svg[svg.find("<svg"):] if "<svg" in svg else svg


def mol_svg(smiles: str, width: int = 360, height: int = 260, theme: str = "light") -> str | None:
    from rdkit.Chem.Draw import rdMolDraw2D

    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    _svg_options(drawer, theme)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return _clean_svg(drawer.GetDrawingText())


def reaction_svg(reaction_smiles: str, width: int = 760, height: int = 220, theme: str = "light") -> str | None:
    from rdkit.Chem.Draw import rdMolDraw2D

    try:
        rxn = AllChem.ReactionFromSmarts(reaction_smiles, useSmiles=True)
    except Exception:
        return None
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    _svg_options(drawer, theme)
    drawer.DrawReaction(rxn)
    drawer.FinishDrawing()
    return _clean_svg(drawer.GetDrawingText())


def reaction_png(reaction_smiles: str, size: tuple[int, int] = (700, 200)) -> bytes | None:
    try:
        rxn = AllChem.ReactionFromSmarts(reaction_smiles, useSmiles=True)
        img = Draw.ReactionToImage(rxn, subImgSize=(size[0] // 4, size[1]))
    except Exception:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
