import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

clr.AddReference('RevitServices')
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

collector = FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements()

resultados = []

def resolver_valor_material(param):
    """Extrae el nombre ya sea si es ElementId o texto plano."""
    if param is None or not param.HasValue:
        return None
    
    # Caso A: ElementId apuntando a Material de Revit
    m_id = param.AsElementId()
    if m_id != ElementId.InvalidElementId:
        mat_elem = doc.GetElement(m_id)
        if mat_elem and hasattr(mat_elem, "Name"):
            return mat_elem.Name
            
    # Caso B: Texto directo (común en familias MEP como Pavco)
    str_val = param.AsString()
    if str_val and str_val.strip():
        return str_val.strip()
        
    return None

def buscar_en_parametros(elem):
    """Busca cualquier parámetro de material ignorando mayúsculas/minúsculas."""
    if elem is None:
        return None
    for p in elem.Parameters:
        p_def = p.Definition
        if not p_def:
            continue
        p_name = p_def.Name.lower()
        if "material" in p_name:
            val = resolver_valor_material(p)
            if val:
                return val
    return None

TransactionManager.Instance.EnsureInTransaction(doc)

for e in collector:
    try:
        if e.Category is None:
            continue

        param_destino = e.LookupParameter("MATERIAL INTEGRADO")
        if param_destino is None or param_destino.IsReadOnly:
            continue

        nombre_mat = None
        type_id = e.GetTypeId()
        e_type = doc.GetElement(type_id) if type_id != ElementId.InvalidElementId else None

        # ESTRATEGIA 1: Estructuras compuestas (Muros, Suelos, Techos)
        if e_type is not None and hasattr(e_type, "GetCompoundStructure"):
            comp_struc = e_type.GetCompoundStructure()
            if comp_struc is not None:
                layers = comp_struc.GetLayers()
                if layers:
                    m_id = layers[0].MaterialId
                    if m_id != ElementId.InvalidElementId:
                        mat_elem = doc.GetElement(m_id)
                        if mat_elem:
                            nombre_mat = mat_elem.Name

        # ESTRATEGIA 2: Tipo de familia (cubre `material`, `Material`, texto y IDs)
        if not nombre_mat and e_type is not None:
            nombre_mat = buscar_en_parametros(e_type)

        # ESTRATEGIA 3: Parámetros en Instancia
        if not nombre_mat:
            nombre_mat = buscar_en_parametros(e)

        # ESTRATEGIA 4: Geometría física (sólidos sin parámetro expuesto)
        if not nombre_mat:
            geom_mat_ids = e.GetMaterialIds(False)
            if geom_mat_ids:
                mat_elem = doc.GetElement(list(geom_mat_ids)[0])
                if mat_elem:
                    nombre_mat = mat_elem.Name

        # ESCRIBIR RESULTADO
        if nombre_mat:
            param_destino.Set(str(nombre_mat))
            resultados.append(f"{e.Category.Name}: {nombre_mat}")

    except Exception:
        continue

TransactionManager.Instance.TransactionTaskDone()

OUT = f"Se procesaron {len(resultados)} materiales con éxito." if resultados else "No se encontraron materiales para asignar."
