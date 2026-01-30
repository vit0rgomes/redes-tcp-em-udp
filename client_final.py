import sys
import json
import socket

# ======================================================================================
# Seção de Configuração e Constantes
# ======================================================================================

server_address_port = ("127.0.0.1", 20001)
buffer_size         = 1024
ISN                 = 10000

# ======================================================================================
# Estrutura de Dados do Pacote
# ======================================================================================

pct_zero = {
    'seq'       : 0,
    'ack'       : 0,
    'rwnd'      : 1024,
    'SYN'       : False,
    'FIN'       : False,
    'payload'   : ""
}

# ======================================================================================
# Funções de Criptografia (Cifra de César)
# ======================================================================================

def caesar_cipher(text, shift=3):
    encrypted_text = ""
    for char in text:
        if 'a' <= char <= 'z':
            encrypted_text += chr((ord(char) - ord('a') + shift) % 26 + ord('a'))
        elif 'A' <= char <= 'Z':
            encrypted_text += chr((ord(char) - ord('A') + shift) % 26 + ord('A'))
        else:
            encrypted_text += char
    return encrypted_text

def caesar_decipher(text, shift=3):
    return caesar_cipher(text, -shift)

# ======================================================================================
# Funções Auxiliares de Empacotamento/Desempacotamento
# ======================================================================================

def my_encode_and_send(socket, msg, adress_port):
    msg_copy = msg.copy()
    if 'payload' in msg_copy and msg_copy['payload']:
        msg_copy['payload'] = caesar_cipher(msg_copy['payload'])
    socket.sendto(json.dumps(msg_copy).encode('utf-8'), adress_port)

def my_receive_and_decode(socket, buffer_size):
    pct, address = socket.recvfrom(buffer_size)
    msg = json.loads(pct.decode('utf-8'))
    if 'payload' in msg and msg['payload']:
        msg['payload'] = caesar_decipher(msg['payload'])
    return msg, address

# ======================================================================================
# Lógica do 3-Way-Handshake (Estabelecimento da Conexão)
# ======================================================================================

def initConnection(adress_port, buffer_size, pct, ISN):
    
    UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    print(f"   {'Cliente':<47} {'Servidor'}")
    print(f"   |{' '*46}|")

    ##### 1ª VIA (Cliente -> Servidor) ##### 
    syn1_msg = pct.copy()
    syn1_msg["SYN"] = True
    syn1_msg["seq"] = ISN
    
    info = f"SYN (seq={ISN})"
    print(f"   |─────── {info:<30} ────▶|")
    
    my_encode_and_send(UDPClientSocket, syn1_msg, adress_port)

    ##### 2ª VIA (Servidor -> Cliente) #####
    syn2_ack_msg, _ = my_receive_and_decode(UDPClientSocket, buffer_size)

    info = f"SYN-ACK (seq={syn2_ack_msg['seq']}, ack={syn2_ack_msg['ack']})"
    print(f"   |◀────── {info:<30} ───────|")

    ##### 3ª VIA (Cliente -> Servidor) #####
    seq_recebido = syn2_ack_msg["seq"]
    ack_recebido = syn2_ack_msg["ack"]

    syn3_ack_msg = syn2_ack_msg.copy()
    syn3_ack_msg["ack"] = seq_recebido + 1
    syn3_ack_msg["seq"] = ack_recebido
    syn3_ack_msg["SYN"] = False

    info = f"ACK (seq={syn3_ack_msg['seq']}, ack={syn3_ack_msg['ack']})"
    print(f"   |─────── {info:<30} ────▶|")
    
    print(f"   |{' '*46}|")
    print(f"   └──────────── CONEXÃO ESTABELECIDA ────────────┘")

    my_encode_and_send(UDPClientSocket, syn3_ack_msg, adress_port)

    now_ack = syn3_ack_msg["ack"]
    
    return UDPClientSocket, now_ack, ack_recebido

# ======================================================================================
# Lógica Principal de Recebimento de Dados - COM BUFFER
# ======================================================================================

def receive_and_ack(connection, address, pct_zero, initial_ack, last_ack):

    expected_seq = initial_ack
    pcts_since_ack = 0
    
    out_of_order_buffer = {}  # {seq: (payload, payload_size)}
    
    received_count = 0
    discarded_count = 0
    ack_sent_count = 0
    buffered_count = 0
    
    connection.settimeout(0.1) 
    
    def send_ack(reason=""):
        nonlocal ack_sent_count, pcts_since_ack
        ack_pct = pct_zero.copy()
        ack_pct["ack"] = expected_seq
        ack_pct["seq"] = last_ack
        
        my_encode_and_send(connection, ack_pct, address)
        ack_sent_count += 1
        
        info = f"ACK (ack={expected_seq})"
        print(f"   |─────── {info:<30} ────▶|  ({reason})")
        
        pcts_since_ack = 0
    
    def process_buffered_packets():
        nonlocal expected_seq, pcts_since_ack, received_count, buffered_count
        
        while expected_seq in out_of_order_buffer:
            payload, payload_size = out_of_order_buffer[expected_seq]
            del out_of_order_buffer[expected_seq]
            
            received_count += 1
            print(f"   |  [BUFFER] Processando seq={expected_seq}")
            
            expected_seq += payload_size
            pcts_since_ack += 1
    
    while True:
        try:
            msg, _ = my_receive_and_decode(connection, buffer_size)
            
            if msg["FIN"]:
                if pcts_since_ack > 0:
                    send_ack("ACK final antes de FIN")
                finishConnection(connection, address, pct_zero, msg["seq"], last_ack)
                break
            
            seq = msg["seq"]
            payload = msg["payload"]
            payload_size = len(caesar_cipher(payload).encode('utf-8')) if payload else 0

            info = f"DADOS (seq={seq})"
            
            if seq == expected_seq:
                # PACOTE EM ORDEM
                received_count += 1
                print(f"   |◀────── {info:<30} ───────|")
                
                expected_seq += payload_size
                pcts_since_ack += 1
                
                process_buffered_packets()
            
            elif seq > expected_seq:
                # PACOTE FORA DE ORDEM
                if seq not in out_of_order_buffer:
                    # Guarda no buffer
                    out_of_order_buffer[seq] = (payload, payload_size)
                    buffered_count += 1
                    print(f"   |◀────── {info:<30} ───────| [!] Fora de ordem (bufferizado)")
                else:
                    # Já está no buffer (duplicado)
                    print(f"   |◀────── {info:<30} ───────| [!] Duplicado")
                
                # Envia ACK duplicado
                send_ack("PERDA DETECTADA - ACK duplicado")
            
            else: # seq < expected_seq
                # PACOTE DUPLICADO (já foi processado antes)
                print(f"   |◀────── {info:<30} ───────| [!] Duplicado")
                send_ack("DUPLICADO - reenviando ACK")
        
        except socket.timeout:
            if pcts_since_ack > 0:
                send_ack(f"FIM DE ESPERA (recebeu {pcts_since_ack} pacote(s))")
        
        except Exception as e:
            print(f"Erro: {e}")
            break
    
    # Estatísticas finais
    print(f"\n{'='*80}")
    print(f"ESTATÍSTICAS FINAIS")
    print(f"{ '='*80}\n")
    print(f"  Pacotes recebidos em ordem: {received_count}")
    print(f"  Pacotes bufferizados (fora de ordem): {buffered_count}")
    print(f"  Total de ACKs enviados: {ack_sent_count}")
    print(f"  Último SEQ confirmado: {expected_seq}")
    print(f"  Pacotes ainda no buffer: {len(out_of_order_buffer)}")
    print(f"{ '='*80}\n")

# ======================================================================================
# Lógica da Finalização da Conexão
# ======================================================================================

def finishConnection(socket, address, pct_zero, now_seq, last_ack):
    
    print(f"   |{' '*46}|")
    
    info_fin = f"FIN (seq={now_seq})"
    print(f"   |◀────── {info_fin:<30} ───────|")
    
    fin_pct = pct_zero.copy()
    now_ack = now_seq + 1
    fin_pct["ack"] = now_ack
    fin_pct["seq"] = last_ack
    fin_pct["FIN"] = True
    
    info_ack = f"FIN-ACK (seq={last_ack}, ack={now_ack})"
    print(f"   |─────── {info_ack:<30} ────▶|")
    print(f"   └──────────── CONEXÃO ENCERRADA ────────────┘")
    
    my_encode_and_send(socket, fin_pct, address)
    
    socket.settimeout(2.0)

    try:
        _, _ = my_receive_and_decode(socket, 1024)
        print("[Info] Recebi retransmissão do servidor. Reenviando ACK de encerramento...")
        my_encode_and_send(socket, fin_pct, address)
    
    except socket.timeout:
        print("Timeout. Assumindo conexão encerrada com sucesso.")
            
    except Exception as e:
        pass

    socket.close()
    print("Cliente Offline.")

# ======================================================================================
# Main
# ======================================================================================
if __name__ == "__main__":
    UDPClientSocket = None
    try:
        UDPClientSocket, now_ack, last_ack = initConnection(server_address_port, buffer_size, pct_zero, ISN)
        receive_and_ack(UDPClientSocket, server_address_port, pct_zero, now_ack, last_ack)
    finally:
        if UDPClientSocket:
            try:
                UDPClientSocket.close()
            except:
                pass
