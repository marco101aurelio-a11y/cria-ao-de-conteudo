import os

nodes = []
edges = []
cell_id = 2

def add_node(id_name, value, style, x, y, w, h, parent="1"):
    global cell_id
    nodes.append(f'''<mxCell id="{id_name}" value="{value}" style="{style}" vertex="1" parent="{parent}">
      <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />
    </mxCell>''')

def add_edge(source, target, label="", line_style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"):
    global cell_id
    val_attr = f'value="{label}"' if label else 'value=""'
    edges.append(f'''<mxCell id="EDGE_{source}_{target}" {val_attr} style="{line_style}" edge="1" parent="1" source="{source}" target="{target}">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>''')

# Swimlanes
sl_style = "swimlane;horizontal=0;whiteSpace=wrap;html=1;"
add_node("pool1", "1. GESTOR", sl_style+"fillColor=#f9d0c4;strokeColor=#b85450;", 20, 20, 1300, 220)
add_node("pool2", "2. PLANEJAMENTO", sl_style+"fillColor=#e2f0d9;strokeColor=#82b366;", 20, 240, 1300, 120)
add_node("pool3", "3. CONTEÚDO", sl_style+"fillColor=#dae8fc;strokeColor=#6c8ebf;", 20, 360, 1300, 120)
add_node("pool4", "4. COMERCIAL", sl_style+"fillColor=#fff2cc;strokeColor=#d6b656;", 20, 480, 1300, 120)
add_node("pool5", "5. CRM", sl_style+"fillColor=#e1d5e7;strokeColor=#9673a6;", 20, 600, 1300, 120)

# Styles
task = "rounded=1;whiteSpace=wrap;html=1;"
start_ev = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1"
end_ev = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#f8cecc;strokeColor=#b85450;border=2;fontStyle=1"
gateway = "rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"
db = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#dae8fc;strokeColor=#6c8ebf;"

# Gestor Nodes (parent=pool1 but since we use global coordinates for ease, we can just use parent=1)
# Actually if we use parent=pool1, x and y are relative to the pool.
# Let's use parent=1 for all elements and place them absolutely.
add_node("n_start", "Início", start_ev, 100, 110, 40, 40)
add_node("n_colfb", "Coletar Feedbacks\nSemanais", task, 200, 100, 120, 60)
add_node("n_db", "BD Métricas", db, 215, 170, 90, 60)
add_node("n_analisar", "Analisar Dados", task, 380, 100, 120, 60)
add_node("n_decisao", "Dados\nSuficientes?", gateway, 540, 90, 80, 80)
add_node("n_aprofundar", "Aprofundar\nColeta", task, 520, 180, 120, 50)
add_node("n_pesq_viral", "Pesquisa Viral", task, 680, 100, 120, 60)
add_node("n_playbook", "Criar Playbook", task, 860, 100, 120, 60)
add_node("n_notificar", "Notificar Equipe", end_ev, 1050, 110, 40, 40)

# Planejamento
add_node("n_plan", "Planejamento\n(4 Agentes IA)", task, 1010, 270, 120, 60)

# Conteudo
add_node("n_pesq_ref", "Pesquisa Refs", task, 1010, 390, 120, 60)
add_node("n_script", "Script (IA)", task, 820, 390, 120, 60)
add_node("n_gravacao", "Gravação", task, 630, 390, 120, 60)
add_node("n_edicao", "Edição (CapCut)", task, 440, 390, 120, 60)
add_node("n_public", "Publicação\nTikTok", task, 250, 390, 120, 60)
add_node("n_distrib", "Distrib. Orgânica", task, 80, 390, 120, 60)

# Comercial
add_node("n_landing", "Pg de Captura", task, 80, 510, 120, 60)
add_node("n_oferta", "Oferta(Cliente)", task, 250, 510, 120, 60)
add_node("n_check", "Checkout", task, 440, 510, 120, 60)
add_node("n_reinvest", "Reinvestimento\nTráfego", end_ev, 660, 520, 40, 40)

# CRM
add_node("n_tag", "Tag / HubSpot", task, 80, 630, 120, 60)
add_node("n_qualif", "Filtros Qualif", task, 250, 630, 120, 60)
add_node("n_email", "Email/Pop-Up", task, 440, 630, 120, 60)
add_node("n_upsell", "Upsell", task, 630, 630, 120, 60)
add_node("n_loop", "Creator\nFlywheel", end_ev, 850, 640, 50, 50)


# Edges
edge_style = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeWidth=2;"
edge_dashed = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeWidth=2;dashed=1;"

# gestor
add_edge("n_start", "n_colfb", "", edge_style)
add_edge("n_colfb", "n_analisar", "", edge_style)
add_edge("n_colfb", "n_db", "", edge_dashed)
add_edge("n_analisar", "n_decisao", "", edge_style)
add_edge("n_decisao", "n_aprofundar", "Não", edge_style)
add_edge("n_aprofundar", "n_analisar", "", edge_style)
add_edge("n_decisao", "n_pesq_viral", "Sim", edge_style)
add_edge("n_pesq_viral", "n_playbook", "", edge_style)
add_edge("n_playbook", "n_notificar", "", edge_style)

# inter pool
add_edge("n_notificar", "n_plan", "", edge_dashed)
add_edge("n_plan", "n_pesq_ref", "", edge_style)

# conteudo
add_edge("n_pesq_ref", "n_script", "", edge_style)
add_edge("n_script", "n_gravacao", "", edge_style)
add_edge("n_gravacao", "n_edicao", "", edge_style)
add_edge("n_edicao", "n_public", "", edge_style)
add_edge("n_public", "n_distrib", "", edge_style)

# comercial
add_edge("n_distrib", "n_landing", "", edge_style)
add_edge("n_landing", "n_oferta", "", edge_style)
add_edge("n_oferta", "n_check", "", edge_style)
add_edge("n_check", "n_reinvest", "Loop", edge_dashed)

# CRM
add_edge("n_landing", "n_tag", "", edge_dashed)
add_edge("n_tag", "n_qualif", "", edge_style)
add_edge("n_qualif", "n_email", "", edge_style)
add_edge("n_email", "n_upsell", "", edge_style)
add_edge("n_upsell", "n_loop", "", edge_style)


xml_out = f"""<mxfile host="Electron" type="device">
  <diagram name="Fluxograma BPMN 2.0" id="BPMN-OPERACAO">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" fold="1" page="1" pageScale="1" pageWidth="1500" pageHeight="1000" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        {chr(10).join(nodes)}
        {chr(10).join(edges)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

with open('fluxograma_operacao_bpmn.drawio', 'w', encoding='utf-8') as f:
    f.write(xml_out)

