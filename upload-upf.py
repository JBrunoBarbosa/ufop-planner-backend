from flask import Flask, request, jsonify
import fitz
import re
import pandas as pd
import tabula

app = Flask(__name__)

def extrair_materias_do_pdf(pdf_path):
    # Extrair texto do PDF usando PyMuPDF
    texto_pdf = ""
    with fitz.open(pdf_path) as pdf_document:
        for page in pdf_document:
            texto_pdf += page.get_text()

    # Encontrar correspondências na segunda tabela usando regex
    padrao_disciplina = r"([A-Z]+\d+)\s+(\d+)\s+([^\n]+)"
    matches = re.findall(padrao_disciplina, texto_pdf)

    # Mapear códigos de disciplina para nomes
    codigo_disciplina_para_nome = {code: name.strip() for code, _, name in matches}

    # Extrair dados da tabela usando tabula
    dfs = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True, stream=True, encoding='utf-8')

    # Definir o nome das colunas
    colunas = ['Horário', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
    df_principal = dfs[0]
    df_principal.columns = colunas

    # Inicializar dicionário para armazenar os dados formatados por dia da semana
    dias_da_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
    materias_por_dia = {dia: [] for dia in dias_da_semana}

    # Iterar sobre as linhas do DataFrame para extrair informações
    for _, row in df_principal.iterrows():
        horario = row['Horário']
        for dia in dias_da_semana:
            codigo_disciplina = row[dia]  # Código da disciplina
            if pd.notna(codigo_disciplina):  # Verificar se há um código de disciplina presente
                # Extrair informações de horário e código da disciplina
                horario_inicio, horario_fim = map(str.strip, horario.split('-'))
                codigo_disciplina, turma = map(str.strip, re.split(r'[-\s]+', codigo_disciplina, maxsplit=1))
                # Usar o código da disciplina para encontrar o nome correspondente
                nome_disciplina = codigo_disciplina_para_nome.get(codigo_disciplina, f'Disciplina {codigo_disciplina}')
                # Combinar o nome da disciplina com a informação da turma para criar o nome completo da disciplina
                nome_completo = f'{nome_disciplina}'
                materias_por_dia[dia].append({
                    'time': f'{horario_inicio} - {horario_fim}',
                    'code': f'{codigo_disciplina} - {turma}',
                    'disciplineName': nome_completo.title()
                })

    return materias_por_dia

def agrupar_disciplinas_iguais(materias_por_dia):
    materias_agrupadas = {}
    for dia, materias in materias_por_dia.items():
        materias_agrupadas[dia] = []
        codigos_adicionados = set()
        for materia in materias:
            codigo_disciplina = materia['code']
            if codigo_disciplina not in codigos_adicionados:
                materias_agrupadas[dia].append(materia)
                codigos_adicionados.add(codigo_disciplina)
    return materias_agrupadas

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "Arquivo PDF não encontrado"}), 400

    pdf_file = request.files['pdf']
    pdf_path = "temp.pdf"  # Salvar o arquivo temporariamente
    pdf_file.save(pdf_path)

    # Extrair informações do PDF
    materias_por_dia = extrair_materias_do_pdf(pdf_path)

    # Agrupar disciplinas idênticas e manter apenas o primeiro horário
    materias_agrupadas = agrupar_disciplinas_iguais(materias_por_dia)

    # Formatar os dados para retorno
    resultado_formatado = formatar_dados_para_retorno(materias_agrupadas)

    # Configurar o Flask para retornar UTF-8 no JSON
    response = jsonify(resultado_formatado)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'

    return response

def formatar_dados_para_retorno(materias_por_dia):
    resultado = {
        "disciplineNames": [],  # Adicionando a chave "disciplineNames"
        "weekDays": []
    }

    for dia_semana, materias in materias_por_dia.items():
        resultado_dia = {
            "day": dia_semana,
            "schedules": []
        }

        for materia in materias:
            resultado["disciplineNames"].append(materia["disciplineName"])  # Adicionando nomes das disciplinas
            resultado_dia['schedules'].append({
                "code": materia['code'],
                "disciplineName": materia['disciplineName'].title(),
                "time": materia['time'].split(' - ')[0]
            })

        resultado["weekDays"].append(resultado_dia)

    # Removendo nomes de disciplinas duplicados
    resultado["disciplineNames"] = list(set(resultado["disciplineNames"]))

    return resultado

if __name__ == '__main__':
    app.run(debug=True)