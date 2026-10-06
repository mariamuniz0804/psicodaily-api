from flask import Blueprint, jsonify, request
from database.db import get_connection
from funcao import decodificar_token
from jwt import ExpiredSignatureError, InvalidTokenError


avaliacoes_bp = Blueprint(
    'avaliacoes',
    __name__,
    url_prefix='/api/avaliacoes'
)


@avaliacoes_bp.route('/', methods=['POST'])
def criar_avaliacao():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({
            'error': 'Token de autenticação necessário'
        }), 401

    con = None
    cur = None

    try:
        payload = decodificar_token(token)

        usuario_id = payload.get('id_usuario')
        papel = payload.get('usuario_role')

        if not usuario_id:
            return jsonify({
                'error': 'Token invalido'
            }), 401

        if papel != 'PACIENTE':
            return jsonify({
                'error': 'Somente pacientes podem avaliar consultas'
            }), 403

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                'error': 'Formato invalido'
            }), 400

        sessao_id = data.get('sessao_id')
        nota = data.get('nota')
        comentario = data.get('comentario')
        publico = data.get('publico', False)

        if not sessao_id or nota is None:
            return jsonify({
                'error': 'Sessao e nota sao obrigatorios'
            }), 400

        try:
            nota = int(nota)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'A nota deve ser um numero entre 1 e 5'
            }), 400

        if nota < 1 or nota > 5:
            return jsonify({
                'error': 'A nota deve ser entre 1 e 5'
            }), 400

        if not isinstance(publico, bool):
            return jsonify({
                'error': 'O campo publico deve ser verdadeiro ou falso'
            }), 400

        if comentario is not None:
            if not isinstance(comentario, str):
                return jsonify({
                    'error': 'Comentario invalido'
                }), 400

            comentario = comentario.strip()

            if len(comentario) > 1000:
                return jsonify({
                    'error': 'O comentario deve ter no maximo 1000 caracteres'
                }), 400

            if not comentario:
                comentario = None

        con = get_connection()
        cur = con.cursor()

        cur.execute('''
            SELECT
                SESSAO_ID,
                PACIENTE_ID,
                PROFISSIONAL_ID,
                STATUS
            FROM SESSAO
            WHERE SESSAO_ID = ?
        ''', (sessao_id,))

        sessao = cur.fetchone()

        if sessao is None:
            return jsonify({
                'error': 'Sessao nao encontrada'
            }), 404

        sessao_id_banco = sessao[0]
        paciente_id = sessao[1]
        profissional_id = sessao[2]
        status = sessao[3]

        if paciente_id != usuario_id:
            return jsonify({
                'error': 'Voce nao pode avaliar esta sessao'
            }), 403

        if status != 'REALIZADO':
            return jsonify({
                'error': 'Somente consultas realizadas podem ser avaliadas'
            }), 409

        cur.execute('''
            SELECT AVALIACAO_ID
            FROM AVALIACAO
            WHERE SESSAO_ID = ?
        ''', (sessao_id_banco,))

        if cur.fetchone() is not None:
            return jsonify({
                'error': 'Esta sessao ja foi avaliada'
            }), 409

        cur.execute('''
            INSERT INTO AVALIACAO (
                SESSAO_ID,
                NOTA,
                COMENTARIO,
                PUBLICO
            )
            VALUES (?, ?, ?, ?)
            RETURNING *
        ''', (
            sessao_id_banco,
            nota,
            comentario,
            1 if publico else 0
        ))

        avaliacao = cur.fetchone()

        colunas = [
            coluna[0].lower()
            for coluna in cur.description
        ]

        resultado = {
            coluna: valor.isoformat()
            if hasattr(valor, 'isoformat')
            else valor
            for coluna, valor in zip(colunas, avaliacao)
        }

        con.commit()

        return jsonify({
            'message': 'Avaliacao criada com sucesso',
            'avaliacao': resultado
        }), 201

    except ExpiredSignatureError:
        return jsonify({
            'error': 'Token expirado'
        }), 401

    except InvalidTokenError:
        return jsonify({
            'error': 'Token invalido'
        }), 401

    except Exception as erro:
        if con is not None:
            con.rollback()

        print(f'[{__name__}]: {erro}')

        return jsonify({
            'error': 'Nao foi possivel criar a avaliacao'
        }), 500

    finally:
        if cur is not None:
            cur.close()

        if con is not None:
            con.close()