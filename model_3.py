import csv
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score, # Importar f1_score
    confusion_matrix,
    roc_curve,
    auc,
    precision_recall_curve,
    classification_report # Para el reporte de clasificacion completo
)
import pickle

# FUNCION: ENTRENAR Y EVALUAR UN MODELO
def entrenar_y_evaluar_modelo(csv_filename, model_output_filename):
    """
    Carga los datos de un CSV, entrena varios modelos de clasificacion, los evalua,
    selecciona el modelo con la mejor exactitud (accuracy) y lo guarda.
    Ademas, calcula y devuelve metricas detalladas y datos para visualizaciones.

    :param csv_filename: Ruta al archivo CSV con los datos de landmarks.
    :param model_output_filename: Nombre del archivo donde se guardara el mejor modelo entrenado (.pkl).
    :return: Un diccionario con metricas y datos para graficos, o None si hay un error.
    """
    print(f"\n--- Procesando dataset: {csv_filename} ---")
    try:

        df = pd.read_csv(csv_filename)

    except FileNotFoundError:

        print(f"Error: El archivo '{csv_filename}' no se encontro. Asegurate de que el CSV de landmarks existe.")
        return None

    print(f"Cargando datos de '{csv_filename}'. Primeras 5 filas:")
    print(df.head())
    print(f"ultimas 5 filas:")
    print(df.tail())
    print(f"Distribucion de clases:\n{df['class'].value_counts()}")

    if 'class' not in df.columns:

        print(f"Error: El archivo '{csv_filename}' no contiene la columna 'class'.")
        return None
    
    if df['class'].nunique() < 2:

        print(f"Error: El dataset '{csv_filename}' debe contener al menos 2 clases para la clasificacion. Clases encontradas: {df['class'].unique()}")
        return None

    X = df.drop('class', axis=1) # Caracteristicas (landmarks)
    y = df['class'] # Variable objetivo (clase de movimiento)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=1234, stratify=y)
    
    print(f"\nDimensiones de los conjuntos de datos:")
    print(f"X_train: {X_train.shape}, y_train: {y_train.shape}")
    print(f"X_test: {X_test.shape}, y_test: {y_test.shape}")

    pipelines = {
        'lr': make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, solver='liblinear', random_state=1234)), 
        'rc': make_pipeline(StandardScaler(), RidgeClassifier(random_state=1234)), # RidgeClassifier no tiene predict_proba
        'rf': make_pipeline(StandardScaler(), RandomForestClassifier(random_state=1234)),
        'gb': make_pipeline(StandardScaler(), GradientBoostingClassifier(random_state=1234)),
    }

    fit_models = {}
    model_accuracies = {} 
    
    print("\nEntrenando modelos...")
    for algo, pipeline in pipelines.items():

        try:
            model = pipeline.fit(X_train, y_train)
            fit_models[algo] = model
            print(f"Modelo {algo} entrenado.")

            yhat = model.predict(X_test)
            current_accuracy = accuracy_score(y_test, yhat) 
            model_accuracies[algo] = current_accuracy

            # Imprimir todas las metricas para visibilidad
            print(
                f"{algo}: ",
                f"Accuracy: {current_accuracy:.4f}, ",
                f"Precision: {precision_score(y_test, yhat, average='weighted', zero_division=0):.4f}, ",
                f"Recall: {recall_score(y_test, yhat, average='weighted', zero_division=0):.4f}, ",
                f"F1-Score: {f1_score(y_test, yhat, average='weighted', zero_division=0):.4f}"
            )

        except Exception as e:
            print(f"Error al entrenar o evaluar el modelo {algo}: {e}")
            fit_models[algo] = None 

    # Seleccionar el mejor modelo basado en la exactitud
    best_accuracy = -1
    best_model_name = None
    best_model = None

    print("\nDeterminando el mejor modelo...")
    if not model_accuracies:

        print("No se pudieron evaluar modelos para determinar el mejor.")
        return None

    for algo, accuracy in model_accuracies.items():

        if accuracy > best_accuracy:

            best_accuracy = accuracy
            best_model_name = algo
            best_model = fit_models[algo]

    if not best_model:

        print(f"No se encontro un modelo adecuado para guardar para '{csv_filename}'.")
        return None

    with open(model_output_filename, 'wb') as f:

        pickle.dump(best_model, f)

    print(f"\n¡exito! El mejor modelo para '{csv_filename}' es '{best_model_name}' con una exactitud de {best_accuracy:.4f}.")
    print(f"Modelo guardado como '{model_output_filename}'.")

    # CALCULAR Y PREPARAR DATOS PARA EL FRONEND 
    y_pred = best_model.predict(X_test)
    labels = sorted(y.unique()) # Asegura un orden consistente para las etiquetas

    # 1. Metricas Generales del Modelo
    metrics_results = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, average='weighted', zero_division=0),
        "recall": recall_score(y_test, y_pred, average='weighted', zero_division=0),
        "f1_score": f1_score(y_test, y_pred, average='weighted', zero_division=0),
        
    }
    print(f"\nDEBUG: metrics_results: {metrics_results}")

    # 2. Grafico de Barras: Repeticiones Correctas vs. Incorrectas
    # Simplificacion: Repeticiones Correctas = Verdaderos Positivos (o clasificados como "correcta")
    # Repeticiones Incorrectas = Falsos Positivos + Falsos Negativos (o mal clasificados)
    
    # Intentamos identificar la clase 'correcta' heuristicamente (ej. 'correct', 'correcta_sentadilla')
    correct_class_label = None
    for label in labels:

        if 'correct' in label.lower():
            correct_class_label = label
            break
    
    num_correct_reps = 0
    num_incorrect_reps = 0

    if correct_class_label:

        num_correct_reps = sum(1 for true_val, pred_val in zip(y_test, y_pred) if true_val == correct_class_label and pred_val == correct_class_label)
        num_incorrect_reps = sum(1 for pred_val in y_pred if pred_val != correct_class_label)

    else:

        print("Advertencia: No se pudo identificar una clase 'correcta' clara para el conteo de repeticiones. Usando aproximación.")
        num_correct_reps = int(metrics_results['accuracy'] * len(y_test))
        num_incorrect_reps = len(y_test) - num_correct_reps # Aquí la aproximación sigue siendo la original, ya que no hay una 'correct_class_label' definida.


    chart_data_reps = {
        "labels": ["Repeticiones Correctas", "Repeticiones Incorrectas"],
        "values": [int(num_correct_reps), int(num_incorrect_reps)], # Asegurarse de que sean enteros
        "chart_title": f"Rendimiento de Repeticiones para {os.path.basename(csv_filename).replace('coords_', '').replace('.csv', '').replace('_', ' ').title()}"
    }
    print(f"DEBUG: chart_data_reps: {chart_data_reps}")

    # 3. Matriz de Confusion (Heatmap)
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    confusion_matrix_data = {
        "labels": [f"Real {label}" for label in labels],
        "prediction_labels": [f"Pred. {label}" for label in labels],
        "matrix": cm.tolist(), # Convertir a lista de listas para JSON
        "chart_title": "Matriz de Confusion"
    }
    print(f"DEBUG: confusion_matrix_data: {confusion_matrix_data}")

    # 4. Curva ROC y AUC
    roc_data = {
        "fpr": [],
        "tpr": [],
        "auc": 0,
        "chart_title": "Curva ROC y AUC"
    }

    # 5. Curva Precision-Recall
    pr_data = {
        "recall": [],
        "precision": [],
        "chart_title": "Curva Precision-Recall"
    }

    # Solo calculamos ROC y PR si el modelo tiene 'predict_proba'
    if hasattr(best_model, 'predict_proba'):

        # Comprobar si el modelo es un clasificador binario o multiclase
        if len(labels) == 2:

            print("DEBUG: Calculando ROC/PR para clasificador binario.")
            y_score = best_model.predict_proba(X_test)[:, 1] # Probabilidades para la clase positiva (la segunda en 'labels')
            fpr, tpr, _ = roc_curve(y_test, y_score, pos_label=labels[1])
            roc_auc = auc(fpr, tpr)
            roc_data = {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "auc": round(roc_auc, 4),
                "chart_title": f"Curva ROC para {labels[1]} vs {labels[0]}"
            }

            precision, recall, _ = precision_recall_curve(y_test, y_score, pos_label=labels[1])
            pr_data = {
                "recall": recall.tolist(),
                "precision": precision.tolist(),
                "chart_title": f"Curva Precision-Recall para {labels[1]}"
            }

        elif len(labels) > 2:

            print("DEBUG: Calculando ROC/PR (OvR) para clasificador multiclase. Usando la primera clase como positiva para la curva de ejemplo.")
            # Para multiclase, calculamos OvR (One-vs-Rest) ROC y AUC.
            # Aquí se simplifica para una única curva, típicamente para una clase de interés
            # o se promedia (macro/micro) si se necesita una sola curva representativa.
           
            if labels: # Asegurarse de que 'labels' no esté vacío

                y_one_hot = pd.get_dummies(y_test) # One-hot encode y_test
                y_prob = best_model.predict_proba(X_test)

                # Encontrar el índice de la primera clase para usar como "positiva" para la curva
                pos_label_index = y_one_hot.columns.get_loc(labels[0])
                
                fpr, tpr, _ = roc_curve(y_one_hot.iloc[:, pos_label_index], y_prob[:, pos_label_index])
                roc_auc = auc(fpr, tpr)
                roc_data = {
                    "fpr": fpr.tolist(),
                    "tpr": tpr.tolist(),
                    "auc": round(roc_auc, 4),
                    "chart_title": f"Curva ROC (OvR) para '{labels[0]}'" 
                }

                precision, recall, _ = precision_recall_curve(y_one_hot.iloc[:, pos_label_index], y_prob[:, pos_label_index])
                pr_data = {
                    "recall": recall.tolist(),
                    "precision": precision.tolist(),
                    "chart_title": f"Curva Precision-Recall (OvR) para '{labels[0]}'"
                }
            else:

                print("Advertencia: No hay clases definidas para calcular ROC/PR en multiclase.")
                roc_data["chart_title"] = "Curva ROC y AUC (No disponible)"
                roc_data["fpr"] = [0, 1]
                roc_data["tpr"] = [0, 1]
                roc_data["auc"] = 0.5
                pr_data["chart_title"] = "Curva Precision-Recall (No disponible)"
                pr_data["recall"] = [0, 1]
                pr_data["precision"] = [1, 0]
    else:

        print("Advertencia: El mejor modelo no tiene 'predict_proba'. ROC/PR no disponibles, usando datos de fallback.")
        roc_data["chart_title"] = "Curva ROC y AUC (No disponible)"
        roc_data["fpr"] = [0, 1]
        roc_data["tpr"] = [0, 1]
        roc_data["auc"] = 0.5

        pr_data["chart_title"] = "Curva Precision-Recall (No disponible)"
        pr_data["recall"] = [0, 1]
        pr_data["precision"] = [1, 0] # Curva PR basica (alta precision con bajo recall, baja precision con alto recall)
    
    print(f"DEBUG: roc_data: {roc_data}")
    print(f"DEBUG: pr_data: {pr_data}")

    # 6. Reporte de Clasificacion
    report_dict = classification_report(y_test, y_pred, target_names=labels, output_dict=True, zero_division=0)
    
    classification_report_data = {
        "headers": ["Clase", "Precision", "Recall", "F1-Score", "Soporte"],
        "data": []
    }

    for label in labels:

        if label in report_dict:

            class_metrics = report_dict[label]
            classification_report_data["data"].append({
                "Clase": label,
                "Precision": class_metrics["precision"],
                "Recall": class_metrics["recall"],
                "F1-Score": class_metrics["f1-score"],
                "Soporte": class_metrics["support"]
            })
    
    # Añadir promedios (macro avg, weighted avg)
    if 'macro avg' in report_dict:

        macro_avg = report_dict['macro avg']
        classification_report_data["data"].append({
            "Clase": "Promedio Macro",
            "Precision": macro_avg["precision"],
            "Recall": macro_avg["recall"],
            "F1-Score": macro_avg["f1-score"],
            "Soporte": macro_avg["support"]
        })
    
    if 'weighted avg' in report_dict:

        weighted_avg = report_dict['weighted avg']
        classification_report_data["data"].append({
            "Clase": "Promedio Ponderado",
            "Precision": weighted_avg["precision"],
            "Recall": weighted_avg["recall"],
            "F1-Score": weighted_avg["f1-score"],
            "Soporte": weighted_avg["support"]
        })

    print(f"DEBUG: classification_report_data: {classification_report_data}")


    # Retornar todos los datos en un solo diccionario
    final_results = {
        "metrics": metrics_results,
        "chart_data_reps": chart_data_reps,
        "confusion_matrix_data": confusion_matrix_data,
        "roc_data": roc_data,
        "pr_data": pr_data,
        "classification_report_data": classification_report_data,
    }
    print(f"DEBUG: Final analysis_results being returned: {final_results.keys()}")
    return final_results

# FUNCION PRINCIPAL PARA CONTROLAR EL FLUJO
def main():
    """
    Funcion principal para orquestar el entrenamiento y evaluacion de modelos
    para multiples datasets de ejercicios.
    """
    print("Iniciando el programa de entrenamiento y evaluacion de modelos de pose.")

    # Configuracion de tus datasets
    datasets = [
        {'name': 'Sentadilla', 'csv_path': '/data/coords_sentadilla.csv', 'model_path': '/models/sentadilla_model.pkl'},
        {'name': 'PesoMuerto', 'csv_path': '/data/coords_peso_muerto.csv', 'model_path': '/models/peso_muerto_model.pkl'},
        {'name': 'PressHombro', 'csv_path': '/data/coords_press_hombro.csv', 'model_path': '/models/press_hombro_model.pkl'},
        {'name': 'Flexion', 'csv_path': '/data/coords_flexiones.csv', 'model_path': '/models/flexiones_model.pkl'},
    ]


    # Entrenar y evaluar modelos para cada dataset
    trained_models_summary = {}
    for dataset_info in datasets:

        exercise_name = dataset_info['name']

        # entrenar_y_evaluar_modelo ahora devuelve un diccionario con los resultados
        results = entrenar_y_evaluar_modelo(dataset_info['csv_path'], dataset_info['model_path'])
        if results:

            trained_models_summary[exercise_name] = f"Modelo guardado en: {dataset_info['model_path']}. Precision: {results['metrics']['accuracy']:.4f}"
        else:
            
            trained_models_summary[exercise_name] = "Entrenamiento fallido o no se encontro el mejor modelo."
    
    print("\n--- Resumen del Entrenamiento ---")
    for name, status in trained_models_summary.items():
        print(f"{name}: {status}")

    print("\nPrograma de entrenamiento y evaluacion finalizado.")

if __name__ == "__main__":
    main()
