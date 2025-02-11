import cv2
import numpy as np
import time
from picamera2 import Picamera2, Preview
from shape_adjustment import ajustar_circulo, ajustar_triangulo, generar_puntos_circulo, generar_puntos_triangulo, plot_circulo, plot_triangulo, euclidean_distance, calcular_semejanza_circulo, generar_puntos_triangulo, calcular_semejanza_triangulo
from shape_detection import detectar_circulo, detectar_triangulo, detectar_octogono, detect_bright_object

if __name__ == "__main__":
    # Inicializar el filtro de Kalman
    kalman = cv2.KalmanFilter(4, 2)
    kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                        [0, 1, 0, 0]], np.float32)
    kalman.transitionMatrix = np.array([[1, 0, 1, 0],
                                        [0, 1, 0, 1],
                                        [0, 0, 1, 0],
                                        [0, 0, 0, 1]], np.float32)
    kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03        

    # Inicializar la cámara
    cap = Picamera2()
    config = cap.create_video_configuration(main={"size": (1280, 720)}, buffer_count=3)
    cap.configure(config)
    cap.start()

    # Inicializar el video de salida
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter('output_video.avi', fourcc, 30.0, (1280, 720))  # 30 FPS, 720p

    stop_detection = False # Parar la detección si se detecta un octógono rojo
    # Inicializar variables para el cálculo de FPS
    prev_frame_time = 0
    new_frame_time = 0

    while not stop_detection:

        frame = cap.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # Convertir de RGB a BGR porque OpenCV usa BGR
        frame = cv2.flip(frame, 1) # Invertir la imagen para que no se vea al revés

        # Calcular FPS
        new_frame_time = time.time()
        fps = 1 / (new_frame_time - prev_frame_time) if new_frame_time != prev_frame_time else 0
        prev_frame_time = new_frame_time
        cv2.putText(frame, f"FPS: {fps:.2f}", (1000, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        # Guardar el frame en el video de salida
        out.write(frame)

        if detectar_octogono(frame):
            stop_detection = True
            break
        
        # Iniciar variables para el seguimiento
        tracking_positions = []
        tracking_started = False
        start_time = None
        initial_position = None

        # Iniciar variables para elegir modo de juego
        circle_found = False
        triangle_found = False
        while not circle_found and not triangle_found:
            frame = cap.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, 1)

            new_frame_time = time.time()
            fps = 1 / (new_frame_time - prev_frame_time) if new_frame_time != prev_frame_time else 0
            prev_frame_time = new_frame_time
            cv2.putText(frame, f"FPS: {fps:.2f}", (1000, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            circle_found = detectar_circulo(frame)

            triangle_found = detectar_triangulo(frame)

            if detectar_octogono(frame):
                stop_detection = True
                break

            cv2.imshow('Seguimiento de Luz', frame)
            out.write(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
        if not stop_detection:
            # Mostrar cuenta atrás antes de iniciar el seguimiento
            for i in range(4, 0, -1):
                for j in range(10):
                    frame = cap.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    frame = cv2.flip(frame, 1)

                    new_frame_time = time.time()
                    fps = 1 / (new_frame_time - prev_frame_time) if new_frame_time != prev_frame_time else 0
                    prev_frame_time = new_frame_time
                    cv2.putText(frame, f"FPS: {fps:.2f}", (1000, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                    cv2.putText(frame, f"Comienza en {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    cv2.imshow('Seguimiento de Luz', frame)
                    out.write(frame)
                    cv2.waitKey(100)

        # Iniciar variables para mostrar la semejanza por pantalla
        show_similarity_score = False
        similarity_score = None
        score_display_start_time = None
        valid_shape = False

        while not stop_detection:
            frame = cap.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, 1)

            new_frame_time = time.time()
            fps = 1 / (new_frame_time - prev_frame_time) if new_frame_time != prev_frame_time else 0
            prev_frame_time = new_frame_time
            cv2.putText(frame, f"FPS: {fps:.2f}", (1000, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)


            if show_similarity_score:
                elapsed_display_time = time.time() - score_display_start_time
                elapsed_time = 0
                # Mostrar la semejanza por pantalla durante 5 segundos
                if elapsed_display_time < 5:
                    if valid_shape:
                        cv2.putText(frame, f"Semejanza: {similarity_score:.2f}", (50, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    else:
                        # Si la forma no es válida, mostrar mensaje de error
                        cv2.putText(frame, "Forma incorrecta. Intente de nuevo.", (50, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                else:
                    # Resetear variables
                    show_similarity_score = False
                    valid_shape = False
                    break
            else:
                # Detectar la posición del objeto brillante
                detected = detect_bright_object(frame)
                if detected:
                    measured = np.array([[np.float32(detected[0])], [np.float32(detected[1])]])
                    kalman.correct(measured)

                    if not tracking_started:
                        tracking_started = True
                        start_time = time.time()
                        initial_position = detected

                predicted = kalman.predict()
                predicted_x, predicted_y = int(predicted[0].item()), int(predicted[1].item())

                if detected:
                    cv2.circle(frame, detected, 10, (0, 255, 0), 2)
                    if tracking_started:
                        tracking_positions.append(detected)

                for i in range(1, len(tracking_positions)):
                    cv2.line(frame, tracking_positions[i - 1], tracking_positions[i], (0, 0, 255), 2)

                cv2.circle(frame, (predicted_x, predicted_y), 10, (255, 0, 0), 2)
                elapsed_time = time.time() - start_time if tracking_started else 0
                cv2.putText(frame, f"Tiempo transcurrido: {elapsed_time:.2f} s", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            if tracking_started and elapsed_time > 1:
                if elapsed_time > 6:
                    print("Demasiado lento")
                    valid_shape = False
                    show_similarity_score = True
                    score_display_start_time = time.time()
                    
                if detected and initial_position and euclidean_distance(detected, initial_position) < 40:
                    if elapsed_time < 2:
                        print("Demasiado rápido")
                        valid_shape = False
                        show_similarity_score = True
                        score_display_start_time = time.time()
                        

                    tracking_positions = [tracking_positions[i] for i in range(len(tracking_positions))
                                        if i == 0 or euclidean_distance(tracking_positions[i], tracking_positions[i - 1]) > 3]

                    if circle_found:
                        circulo = ajustar_circulo(tracking_positions)
                        if circulo[2] < 125:
                            print("Círculo demasiado pequeño")
                            valid_shape = False
                            show_similarity_score = True
                            score_display_start_time = time.time()
                        else:
                            if not show_similarity_score:
                                puntos_circulo = generar_puntos_circulo(circulo[0], circulo[1], circulo[2], len(tracking_positions))
                                semejanza, puntos_unidos = calcular_semejanza_circulo(tracking_positions, puntos_circulo, circulo[2])
                                print("Semejanza:", semejanza)

                                similarity_score = semejanza
                                show_similarity_score = True
                                score_display_start_time = time.time()
                                valid_shape = True
                                # plot_circulo(tracking_positions, puntos_circulo, puntos_unidos)
                    elif triangle_found:
                        vertices = ajustar_triangulo(tracking_positions)
                        if euclidean_distance(vertices[0], vertices[1]) < 50:
                            print("Triángulo demasiado pequeño")
                            valid_shape = False
                            show_similarity_score = True
                            score_display_start_time = time.time()
                        else:
                            if not show_similarity_score:
                                puntos_triangulo = generar_puntos_triangulo(vertices, len(tracking_positions))
                                semejanza, puntos_unidos = calcular_semejanza_triangulo(tracking_positions, puntos_triangulo)
                                print("Semejanza:", semejanza)

                                similarity_score = semejanza
                                show_similarity_score = True
                                score_display_start_time = time.time()
                                valid_shape = True
                                #plot_triangulo(tracking_positions, puntos_triangulo, puntos_unidos)
            cv2.imshow('Seguimiento de Luz', frame)
            out.write(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    # Liberar recursos
    cap.stop()
    out.release()
    cv2.destroyAllWindows()
