import socket
import json
from threading import Thread
from canais import canais
import time

# contador a ser usado como identificador único de cada usuário (zera quando o server reinicia)
contador_id = 0

# função para adicionar um usuário ao dicionário de usuários da classe Servidor, e retorna o id desse usuário
def registra_usuario(dict, nomeHost, socketCliente, canal, nomeUser):
    global contador_id
    contador_id += 1

    #formato do usuário no banco de dados: 
    # int id: str apelido, str hostname, socket, str nome do canal, str nome de usuário
    dict[contador_id] = [f'Usuário{contador_id}', nomeHost, socketCliente, canal, nomeUser]
    return contador_id

# função para encontrar o id de um usuário pelo seu apelido
def encontra_por_apelido(dict, apelido):
    for key in dict:
        if str(dict[key][0]) == str(apelido):
            return key
    return False

# classe que opera o servidor, com suas devidas competências
class Servidor:
    def __init__(self, enderecoServidor='', portaServidor=6667):
        self.nodeID = 1
        self.destino = 'Chatzera'

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # se endereco_servidor = '', então o IP usado será o IP da própria máquina na conexão local
        # a princípio, queremos usar o IP da conexão local mesmo (roteador)
        self.socket.bind((enderecoServidor, portaServidor))

        print(f'Rodando servidor na porta {portaServidor}')
        print(f'nodeID: {self.nodeID} | destino: {self.destino}')

        self.socket.listen()

        # dicionário que armazena os clientes do chat: chave é o id e valor são os dados do usuário
        self.registrosDeUsuarios = {}

        self.iniciar()

    def iniciar(self):
        while True:
            try:
                # servidor aguarda conexões de novos clientes
                socketCliente, enderecoCliente = self.socket.accept()

                # quando estabelecida a conexão, o cliente logo enviará o nome do seu host
                # e seu nome de usuário
                nomesUserAndHost = json.loads(socketCliente.recv(512).decode('utf-8'))
                nomeHost, nomeUser = nomesUserAndHost.split('###')

                idCliente = registra_usuario(self.registrosDeUsuarios, nomeHost, socketCliente, None, nomeUser)

                # espera a thread de escuta do cliente iniciar
                time.sleep(1)
                # envia para o cliente uma resposta confirmando seu cadastro no chat
                msg = {"mensagem": f">> [SERVER]: Seu apelido é {self.registrosDeUsuarios[idCliente][0]}, use o /NICK para alterar\n>> [SERVER]: Você está no canal de espera... Use /LIST e /JOIN para aproveitar o chat"}
                socketCliente.send(json.dumps(msg).encode('utf-8'))

                # inicia a thread de atendimento ao cliente
                thread = Thread(target=self.implementacaoThreadCliente,
                                args=(idCliente, socketCliente),
                                daemon=True)
                thread.start()

            except Exception as e:
                # caso não seja possível estabelecer a conexão com algum cliente
                print(f"Erro ao aceita conexão: {e}")
                print("Servidor desligando thread de escuta e encerrando operações")
                self.socket.close()
                break


    def implementacaoThreadCliente(self, idCliente, socketCliente):
        while True:
            try:
                mensagem = socketCliente.recv(512) # aguarda por mensagem do cliente
                if mensagem:
                    print(f"Servidor recebeu do cliente {idCliente} a mensagem: {json.loads(mensagem.decode('utf-8'))}")

                    # Decodifica mensagem em bytes para utf-8 e
                    # em seguida decodifica a mensagem em Json para um dicionário Python
                    mensagem_decodificada = json.loads(mensagem.decode("utf-8"))

                    # lida com a mensagem e escolhe o que fazer
                    self.handlerDeMensagem(mensagem_decodificada, idCliente, socketCliente)

            except Exception as e:
                # caso o socket tenha a conexão fechada pelo cliente ou algum outro erro ocorra
                canal = self.registrosDeUsuarios[idCliente][3]
                if canal:  
                  canais[canal] -= 1
                print(f"Cliente {idCliente} fechou a conexão com exceção: {e}")
                break


    def handlerDeMensagem(self, mensagem_decodificada, idCliente, socketCliente):
        # resposta que o servidor enviará ao(s) cliente(s)
        resposta = {}

        # formato de mensagem_decodificada: [{"mensagem": ["mensagem", "de", "fato"]}]
        #cmd é a primeira palavra da mensagem_de_fato
        cmd = mensagem_decodificada[0]["mensagem"][0]
        mensagem_de_fato = mensagem_decodificada[0]["mensagem"]

        # flag que decide se a resposta do servidor será transmitida no canal ou só para um cliente
        para_canal = False

        # ========== DAQUI PARA FRENTE SÃO OS CÓDIGOS DOS COMANDOS ============

        if cmd == "/NICK":
            if len(mensagem_de_fato) > 2:
                resposta = {"mensagem": ">> [SERVER]: Error 400: Não utilize espaços no apelido"}
            else:
                novoApelido = mensagem_de_fato[1]
                chave_encontrada = encontra_por_apelido(self.registrosDeUsuarios, novoApelido)
                if chave_encontrada:
                    resposta = {"mensagem" : ">> [SERVER]: Error 400: Apelido já em uso" }
                else:
                    self.registrosDeUsuarios[idCliente][0] = novoApelido
                    resposta = {"mensagem" : ">> [SERVER]: Apelido cadastrado" }
            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd == "/USER":
            if len(mensagem_de_fato) > 1:
                apelido_para_busca = mensagem_de_fato[1]
                chave_encontrada = encontra_por_apelido(self.registrosDeUsuarios, apelido_para_busca)
                if chave_encontrada:
                    apelido = self.registrosDeUsuarios[chave_encontrada][0]
                    nome_real = f'{self.registrosDeUsuarios[chave_encontrada][4]} (id: {chave_encontrada})'
                    nome_host = self.registrosDeUsuarios[chave_encontrada][1]
                    resposta = {"mensagem": f">> [SERVER]: Dados do usuário: apelido: {apelido} | nome: {nome_real} | host: {nome_host[0]}****"}
                else:
                    resposta = {"mensagem": f">> [SERVER]: Error 404: Usuário não encontrado"}
            else:
                apelido = self.registrosDeUsuarios[idCliente][0]
                nome_real = f'{self.registrosDeUsuarios[idCliente][4]} (id: {idCliente})'
                nome_host = self.registrosDeUsuarios[idCliente][1]
                resposta = {"mensagem": f">> [SERVER]: Dados do usuário: apelido: {apelido} | nome: {nome_real} | host: {nome_host[0]}****"}
            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd == "/QUIT":
            apelidoUsuario = self.registrosDeUsuarios[idCliente][0]
            socketCliente.close()
            canalUsuario = self.registrosDeUsuarios[idCliente][3]
            if canalUsuario:
                canais[canalUsuario] -= 1
            resposta = {"mensagem" : f">> [SERVER]: Usuário {apelidoUsuario} saiu do servidor"}
            para_canal = True
            self.envia(resposta, para_canal, idCliente, socketCliente)
            self.registrosDeUsuarios.pop(idCliente)

        elif cmd == "/WHO":
            try:
                # guarda o nome do canal
                canal_desejado = " ".join(mensagem_de_fato[1:])
                # se nao existir um canal com esse nome, a mensagem é de erro
                if canal_desejado not in canais:
                    resposta = {"mensagem": ">> [SERVER]: Error 404: Canal não encontrado"}
                # se existir, verifica pelo dicionario quais usiários estão no canal atualmente
                else:
                    usuarios_do_canal = ""
                    for key in self.registrosDeUsuarios:
                        if self.registrosDeUsuarios[key][3] == canal_desejado:
                            usuarios_do_canal += " " + self.registrosDeUsuarios[key][0]
                    resposta = {"mensagem": f">> [SERVER]: Usuários do canal são: {usuarios_do_canal}"}
            except:
                resposta = {"mensagem": ">> [SERVER]: Error 400: Verifique se digitou o comando corretamente" }

            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd == "/PRIVMSG":
            try:
                achou_apelido = False
                # verifica se o nome apos privmsg é um canal
                if mensagem_de_fato[1] not in canais:
                    # se nao for um canal, verifica se existe um apelido com o nomes digitado
                    for key in self.registrosDeUsuarios:
                        if self.registrosDeUsuarios[key][0] == mensagem_de_fato[1]:
                            # se existir, guarda os dados do usuario com o apelido inputado
                            idCliente_a_ser_enviado = key
                            socketCliente_a_ser_enviado = self.registrosDeUsuarios[key][2]
                            achou_apelido = True
                            break
                    # se achou um usuário, manda a msg pra ele apenas
                    if achou_apelido:
                        resto_da_mensagem = " ".join(mensagem_de_fato[2:])
                        resposta = {"mensagem": f">> [{self.registrosDeUsuarios[idCliente][0]} (privado)]: {resto_da_mensagem}"}
                        self.envia(resposta, para_canal, idCliente_a_ser_enviado, socketCliente_a_ser_enviado)
                    # se nao, nao
                    else:
                        resposta = {"mensagem": "[SERVER]: Error 404: Usuário não encontrado"}
                        self.envia(resposta, para_canal, idCliente, socketCliente)

                else:
                    # se o nome digitado for um canal, o usuário "entra" no canal, manda a mensagem e volta pro seu canal de origem
                    para_canal = True
                    resto_da_mensagem = " ".join(mensagem_de_fato[2:])
                    resposta = {"mensagem": f">> [{self.registrosDeUsuarios[idCliente][0]}]: {resto_da_mensagem}"}
                    canal_original = self.registrosDeUsuarios[idCliente][3]
                    self.registrosDeUsuarios[idCliente][3] = mensagem_de_fato[1]
                    self.envia(resposta, para_canal, idCliente, socketCliente)
                    self.registrosDeUsuarios[idCliente][3] = canal_original
            except:
                resposta = {"mensagem": ">> [SERVER]: Error 400: Verifique se digitou o comando corretamente" }
                self.envia(resposta, para_canal, idCliente, socketCliente)



        ##---------ESSES DEPENDEM DE + DE 1 CANAL---------------#

        elif cmd == "/JOIN":
            try:
                canal_a_entrar = mensagem_de_fato[1]
                if canal_a_entrar in canais:
                    canal_original = self.registrosDeUsuarios[idCliente][3]
                    if canal_original:
                        canais[canal_original] -= 1
                    self.registrosDeUsuarios[idCliente][3] = canal_a_entrar
                    canais[canal_a_entrar] += 1
                    resposta = {"mensagem": f">> [SERVER]: Bem vindo ao canal {canal_a_entrar}"}
                else:
                    resposta = {"mensagem": ">> [SERVER]: Error 404: Canal não encontrado"}
            except:
                resposta = {"mensagem": ">> [SERVER]: Error 400: Digite o canal que deseja entrar"}

            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd == "/PART":
            try:
                # recebe o canal
                canal_a_sair = mensagem_de_fato[1]

                # verifica se ele existe ou nao
                if canal_a_sair not in canais:
                    resposta = {"mensagem": ">> [SERVER]: Error 404: Canal não encontrado"}
                # se ele existir, verifica se o usuário está no canal para poder sair
                else:
                    if self.registrosDeUsuarios[idCliente][3] == canal_a_sair:
                        self.registrosDeUsuarios[idCliente][3] = None
                        canais[canal_a_sair] -= 1
                        resposta = {"mensagem": f">> [SERVER]: Você saiu do canal {canal_a_sair}"}
                    else:
                        resposta = {"mensagem": f">> [SERVER]: Error 400: Você não está no canal {canal_a_sair}"}
            except:
                resposta = {"mensagem": ">> [SERVER]: Error 400: Verifique se digitou o comando corretamente" }
            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd == "/LIST":
            canais_msg = 'Listando canais...'
            for canal, total_users in canais.items():
                canais_msg += f'\n\t{canal}  |  Total de usuários: {total_users}'
            resposta = {"mensagem": f">> [SERVER]: {canais_msg}"}
            self.envia(resposta, para_canal, idCliente, socketCliente)

        elif cmd[0] == "/":
            resposta = {"mensagem" : ">> [SERVER]: ERR UNKNOWNCOMMAND"}
            self.envia(resposta, para_canal, idCliente, socketCliente)

        # caso a mensagem recebida pelo cliente não seja um comando e sim uma comunicação
        # com os demais clientes
        else:
            apelidoUsuario = self.registrosDeUsuarios[idCliente][0]
            resposta = {"mensagem": f">> [{apelidoUsuario}]: " + " ".join(mensagem_de_fato)}
            para_canal = True
            self.envia(resposta, para_canal, idCliente, socketCliente)

    # Método para enviar adequadamente as respostas do servidor
    def envia(self, resposta, para_canal, idCliente, socketCliente):
        # Caso a resposta do servidor tenha que ser transmitida no canal do remetente
        if para_canal:
            # Converte a resposta em uma stream de bits
            resposta_bytes = json.dumps(resposta).encode("utf-8")

            #toma o canal do remetente
            canalCliente = self.registrosDeUsuarios[idCliente][3]

            for usuario in self.registrosDeUsuarios.values():
            # se o remetente estiver em um canal, envia a mensagem para todos deste canal, exceto ele
                if canalCliente and canalCliente == usuario[3] and socketCliente != usuario[2]:
                    usuario[2].send(resposta_bytes)
            print(f'Servidor enviou para os devidos clientes a mensagem: {resposta}')

        # Caso a resposta do servidor interesse apenas ao remetente
        else:
            resposta_bytes = json.dumps(resposta).encode("utf-8")
            socketCliente.send(resposta_bytes)
            print(f"Servidor enviou para o cliente {idCliente} a mensagem: {resposta}")

# Instancia e cria o servidor
servidor = Servidor()
del servidor