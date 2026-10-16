import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from motoratlas.datos import cargar_datos
from motoratlas.rag import MotorRAG, Pregunta, SalidaModelo


class ClienteFalso:
    def __init__(self, vector=None):
        self.llamadas_embeddings = 0
        self.llamadas_respuestas = 0
        self.vector = vector or [1.0, 0.0]
        self.embeddings = SimpleNamespace(create=self.crear_embeddings)
        self.responses = SimpleNamespace(parse=self.responder)

    def crear_embeddings(self, input, **kwargs):
        self.llamadas_embeddings += 1
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=self.vector) for i, _ in enumerate(input)])

    def responder(self, **kwargs):
        self.llamadas_respuestas += 1
        return SimpleNamespace(output_parsed=SalidaModelo(respuesta="Anuncio MA-001", documentos=["MA-001"], no_consta=False))


class PruebasRAG(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "indice.npz"
        self.datos = cargar_datos()

    def motor(self, cliente):
        return MotorRAG(documentos=self.datos, cliente=cliente, ruta=self.ruta)

    def test_corpus_y_coherencia_maquetas(self):
        self.assertEqual(len(self.datos), 68)
        self.assertEqual(len({d['id'] for d in self.datos}), 68)
        self.assertEqual([d['precio_eur'] for d in self.datos[:2]], [15500, 15750])
        self.assertEqual([d['kilometros'] for d in self.datos[:2]], [43000, 34000])
        self.assertTrue(all(d['matricula'] is None for d in self.datos))
        self.assertTrue(all(d['foto_url'] is None for d in self.datos[8:]))
        self.assertEqual(self.datos[0]['ficha_tecnica']['Transmisión secundaria'], 'CARDÁN')

    def test_matricula_sin_ninguna_llamada(self):
        cliente = ClienteFalso()
        motor = self.motor(cliente)
        for pregunta in ('¿Cuál es la matrícula?', 'Dime el número de placa de MA-001', 'Información de matricula de esas dos BMW'):
            respuesta = motor.preguntar(Pregunta(pregunta=pregunta))
            self.assertTrue(respuesta.no_consta)
            self.assertFalse(respuesta.modelo_utilizado)
            self.assertIn('no consta', respuesta.respuesta)
            for fuente in respuesta.fuentes:
                original = next(d for d in self.datos if d['id'] == fuente.documento_id)
                self.assertIn(fuente.fragmento, original['texto'])
        self.assertEqual(cliente.llamadas_respuestas, 0)
        self.assertEqual(cliente.llamadas_embeddings, 0)

    def test_indice_reutilizado_y_cambio_corpus(self):
        cliente = ClienteFalso()
        motor = self.motor(cliente)
        motor.indice.preparar()
        self.assertEqual(cliente.llamadas_embeddings, 1)
        segundo = self.motor(cliente)
        segundo.indice.preparar()
        self.assertTrue(segundo.indice.reutilizado)
        self.assertEqual(cliente.llamadas_embeddings, 1)
        segundo.documentos[0] = dict(segundo.documentos[0], texto='Texto modificado')
        self.motor(cliente).indice.preparar()
        self.assertEqual(cliente.llamadas_embeddings, 2)

    def test_sin_similitud_no_llama_modelo_generativo(self):
        cliente = ClienteFalso()
        motor = self.motor(cliente)
        motor.indice.preparar()
        cliente.vector = [0.0, 1.0]
        respuesta = motor.preguntar(Pregunta(pregunta='¿Cuál es la capital de Mongolia?'))
        self.assertTrue(respuesta.no_consta)
        self.assertEqual(respuesta.fuentes, [])
        self.assertEqual(cliente.llamadas_respuestas, 0)

    def test_modelo_ausente_no_llama_openai(self):
        cliente = ClienteFalso()
        respuesta = self.motor(cliente).preguntar(Pregunta(pregunta='Busco una BMW R 9999 GS'))
        self.assertTrue(respuesta.no_consta)
        self.assertEqual(cliente.llamadas_embeddings, 0)
        self.assertEqual(cliente.llamadas_respuestas, 0)

    def test_historial_resuelve_las_dos_fichas(self):
        motor = self.motor(ClienteFalso())
        peticion = Pregunta(pregunta='¿Qué mantenimiento y equipamiento tienen?', historial=[
            {'role':'user','content':'Busco BMW R 1250 GS hasta 17.000 €. Quiero ficha técnica.'},
            {'role':'assistant','content':'Puedes comparar MA-001 y MA-002.'}])
        candidatos, contexto = motor.candidatos(peticion)
        self.assertEqual({d['id'] for d in candidatos}, {'MA-001', 'MA-002'})
        self.assertIn('17.000', contexto)

    def test_matricula_conserva_los_anuncios_de_la_conversacion(self):
        cliente = ClienteFalso()
        respuesta = self.motor(cliente).preguntar(Pregunta(pregunta='¿Cuál es la matrícula?', historial=[
            {'role':'user', 'content':'Busco BMW R 1250 GS hasta 17.000 €. Quiero ficha técnica.'},
            {'role':'assistant', 'content':'Puedes comparar MA-001 y MA-002.'}]))
        self.assertEqual({f.documento_id for f in respuesta.fuentes}, {'MA-001', 'MA-002'})
        self.assertEqual(cliente.llamadas_respuestas, 0)

    def test_fuentes_inventadas_se_rechazan(self):
        cliente = ClienteFalso()
        cliente.responses.parse = lambda **kwargs: SimpleNamespace(output_parsed=SalidaModelo(
            respuesta='Dato inventado', documentos=['MA-999'], no_consta=False))
        with self.assertRaises(ValueError):
            self.motor(cliente).preguntar(Pregunta(pregunta='Busco BMW R 1250 GS'))

    def test_cache_corrupta_se_reconstruye(self):
        self.ruta.write_bytes(b'archivo corrupto')
        cliente = ClienteFalso()
        motor = self.motor(cliente)
        motor.indice.preparar()
        self.assertEqual(cliente.llamadas_embeddings, 1)
        with np.load(self.ruta, allow_pickle=False) as datos:
            self.assertEqual(datos['vectores'].shape[0], 68)


if __name__ == '__main__':
    unittest.main()
