"""
Script de Calibración de Thresholds Multi-Label
Evalúa el sistema de diagnóstico contra dataset etiquetado manualmente
y sugiere thresholds óptimos por categoría
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import requests
from tabulate import tabulate

# Configuración
DIAGNOSTIC_ENDPOINT = "http://localhost:5000/diagnostic/detect"
DEFAULT_DATASET_PATH = "dataset/ground_truth_labels.json"

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class CalibrationMetrics:
    """Calcula métricas de clasificación por categoría"""

    def __init__(self):
        self.tp = 0  # True Positives
        self.fp = 0  # False Positives
        self.fn = 0  # False Negatives
        self.tn = 0  # True Negatives
        self.scores_positive = []  # Scores cuando debería estar (TP + FN)
        self.scores_negative = []  # Scores cuando NO debería estar (TN + FP)

    def add_result(self, should_detect: bool, was_detected: bool, score: float):
        """Registra un resultado de detección"""
        if should_detect and was_detected:
            self.tp += 1
            self.scores_positive.append(score)
        elif should_detect and not was_detected:
            self.fn += 1
            self.scores_positive.append(score)
        elif not should_detect and was_detected:
            self.fp += 1
            self.scores_negative.append(score)
        else:  # not should_detect and not was_detected
            self.tn += 1
            self.scores_negative.append(score)

    def get_precision(self) -> float:
        """Precisión: TP / (TP + FP)"""
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)

    def get_recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)

    def get_f1(self) -> float:
        """F1-Score: 2 * (Precision * Recall) / (Precision + Recall)"""
        p = self.get_precision()
        r = self.get_recall()
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    def suggest_threshold(self, method='f1_optimal') -> float:
        """
        Sugiere threshold óptimo basado en distribución de scores

        Métodos:
        - 'f1_optimal': Threshold que maximiza F1-score
        - 'percentile_30': Percentil 30 de scores positivos
        - 'mean_positive': Media de scores cuando debería detectarse
        - 'adaptive_gap': Media positivos - 1 std
        """
        if not self.scores_positive:
            return 0.35  # Fallback

        if method == 'percentile_30':
            return float(np.percentile(self.scores_positive, 30))

        elif method == 'mean_positive':
            return float(np.mean(self.scores_positive))

        elif method == 'adaptive_gap':
            mean_pos = np.mean(self.scores_positive)
            std_pos = np.std(self.scores_positive) if len(self.scores_positive) > 1 else 0.05
            return max(0.20, float(mean_pos - std_pos))

        elif method == 'f1_optimal':
            # Buscar threshold que maximiza F1 barriendo rango de scores
            if not self.scores_positive:
                return 0.35

            all_scores = sorted(set(self.scores_positive + self.scores_negative))
            best_f1 = 0.0
            best_threshold = 0.35

            for candidate_th in all_scores:
                # Simular detección con este threshold
                tp = sum(1 for s in self.scores_positive if s >= candidate_th)
                fn = len(self.scores_positive) - tp
                fp = sum(1 for s in self.scores_negative if s >= candidate_th)

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = candidate_th

            return float(best_threshold)

        return 0.35


def load_dataset(dataset_path: str) -> List[Dict]:
    """Carga el dataset etiquetado desde JSON"""
    if not os.path.exists(dataset_path):
        print(f"{Colors.RED}❌ Dataset no encontrado: {dataset_path}{Colors.END}")
        print(f"\n{Colors.YELLOW}💡 Crea el archivo siguiendo la guía en:")
        print(f"   docs/GUIA_PASO_2_DATASET_GROUND_TRUTH.md{Colors.END}\n")
        sys.exit(1)

    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'images' not in data:
        print(f"{Colors.RED}❌ Formato inválido: falta campo 'images'{Colors.END}")
        sys.exit(1)

    return data['images']


def run_diagnostic(image_path: str, multi_label: bool = True) -> Dict:
    """Ejecuta diagnóstico sobre una imagen"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

    with open(image_path, 'rb') as f:
        files = {'image': f}
        data = {'multi_label': '1' if multi_label else '0'}

        response = requests.post(DIAGNOSTIC_ENDPOINT, files=files, data=data)
        response.raise_for_status()
        return response.json()


def evaluate_dataset(dataset: List[Dict], output_dir: str = "calibration_results") -> Dict:
    """Evalúa todo el dataset y calcula métricas por categoría"""

    os.makedirs(output_dir, exist_ok=True)

    # Métricas por categoría
    category_metrics = defaultdict(CalibrationMetrics)

    # Resultados detallados por imagen
    detailed_results = []

    print(f"\n{Colors.BOLD}🔍 Evaluando dataset...{Colors.END}\n")

    for idx, item in enumerate(dataset, 1):
        image_path = item['path']
        expected_categories = set(item['expected_categories'])
        notes = item.get('notes', '')

        print(f"[{idx}/{len(dataset)}] {os.path.basename(image_path)}")
        print(f"   Esperadas: {', '.join(expected_categories)}")

        try:
            # Ejecutar diagnóstico
            result = run_diagnostic(image_path, multi_label=True)

            if not result.get('success'):
                print(f"   {Colors.RED}❌ Error: {result.get('error')}{Colors.END}")
                continue

            # Extraer categorías detectadas y scores
            detected_categories = {}
            all_results = result.get('all_results', [])

            for cat_result in all_results:
                cat_name = cat_result['category_name']
                ml_score = cat_result.get('multi_label_score', 0.0)
                detected_categories[cat_name] = ml_score

            # Categorías que pasaron threshold ML
            passing_ml = result.get('passing_categories_multi_label', [])
            detected_set = set(p['category_name'] for p in passing_ml)

            print(f"   Detectadas: {', '.join(detected_set) if detected_set else '(ninguna)'}")

            # Calcular métricas por categoría
            all_categories = set(expected_categories) | set(detected_categories.keys())

            for cat_name in all_categories:
                should_detect = cat_name in expected_categories
                was_detected = cat_name in detected_set
                score = detected_categories.get(cat_name, 0.0)

                category_metrics[cat_name].add_result(should_detect, was_detected, score)

            # Guardar resultado detallado
            detailed_results.append({
                'filename': os.path.basename(image_path),
                'expected': list(expected_categories),
                'detected': list(detected_set),
                'scores': detected_categories,
                'notes': notes,
                'correct': expected_categories == detected_set
            })

            # Feedback visual
            if expected_categories == detected_set:
                print(f"   {Colors.GREEN}✅ Perfecto{Colors.END}")
            else:
                missed = expected_categories - detected_set
                extra = detected_set - expected_categories
                if missed:
                    print(f"   {Colors.YELLOW}⚠️  Perdió: {', '.join(missed)}{Colors.END}")
                if extra:
                    print(f"   {Colors.YELLOW}⚠️  Extra: {', '.join(extra)}{Colors.END}")

        except Exception as e:
            print(f"   {Colors.RED}❌ Error: {e}{Colors.END}")
            detailed_results.append({
                'filename': os.path.basename(image_path),
                'error': str(e)
            })

        print()

    return {
        'category_metrics': category_metrics,
        'detailed_results': detailed_results,
        'dataset_size': len(dataset)
    }


def generate_report(evaluation_results: Dict, output_dir: str):
    """Genera reporte de calibración con métricas y sugerencias"""

    category_metrics = evaluation_results['category_metrics']
    detailed_results = evaluation_results['detailed_results']
    dataset_size = evaluation_results['dataset_size']

    # ===== REPORTE POR CATEGORÍA =====
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}📊 REPORTE DE CALIBRACIÓN{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

    print(f"Dataset: {dataset_size} imágenes evaluadas\n")

    # Tabla de métricas por categoría
    table_data = []
    threshold_suggestions = {}

    for cat_name in sorted(category_metrics.keys()):
        metrics = category_metrics[cat_name]

        precision = metrics.get_precision()
        recall = metrics.get_recall()
        f1 = metrics.get_f1()

        # Sugerir threshold óptimo
        suggested_th = metrics.suggest_threshold(method='f1_optimal')
        threshold_suggestions[cat_name] = suggested_th

        # Estadísticas de scores
        mean_positive = np.mean(metrics.scores_positive) if metrics.scores_positive else 0.0
        mean_negative = np.mean(metrics.scores_negative) if metrics.scores_negative else 0.0

        table_data.append([
            cat_name,
            f"{precision:.2%}",
            f"{recall:.2%}",
            f"{f1:.2%}",
            f"{suggested_th:.3f}",
            f"{mean_positive:.3f}",
            f"{mean_negative:.3f}",
            f"{metrics.tp}/{metrics.fn}/{metrics.fp}"
        ])

    headers = ["Categoría", "Precisión", "Recall", "F1", "Threshold Sugerido", "Score+ Promedio", "Score- Promedio", "TP/FN/FP"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    # ===== CATEGORÍAS PROBLEMÁTICAS =====
    print(f"\n{Colors.BOLD}⚠️  CATEGORÍAS PROBLEMÁTICAS{Colors.END}\n")

    problematic = []
    for cat_name, metrics in category_metrics.items():
        f1 = metrics.get_f1()
        if f1 < 0.7:  # F1 < 70%
            problematic.append((cat_name, f1, metrics))

    if problematic:
        problematic.sort(key=lambda x: x[1])  # Ordenar por F1 ascendente
        for cat_name, f1, metrics in problematic:
            print(f"• {Colors.YELLOW}{cat_name}{Colors.END}: F1={f1:.2%}")
            if metrics.fn > 0:
                print(f"  → Falsos negativos: {metrics.fn} (aumentar sensibilidad)")
            if metrics.fp > 0:
                print(f"  → Falsos positivos: {metrics.fp} (aumentar threshold)")
    else:
        print(f"{Colors.GREEN}✅ Todas las categorías están bien calibradas (F1 > 70%){Colors.END}")

    # ===== CASOS DE FALLO =====
    failures = [r for r in detailed_results if not r.get('correct', False) and 'error' not in r]

    if failures:
        print(f"\n{Colors.BOLD}❌ CASOS DE FALLO ({len(failures)}){Colors.END}\n")
        for fail in failures[:10]:  # Mostrar primeros 10
            print(f"• {fail['filename']}")
            print(f"  Esperadas: {', '.join(fail['expected'])}")
            print(f"  Detectadas: {', '.join(fail['detected'])}")
            if fail.get('notes'):
                print(f"  Notas: {fail['notes']}")
            print()

    # ===== GUARDAR RESULTADOS =====
    output_file = os.path.join(output_dir, "calibration_results.json")

    results_export = {
        'dataset_size': dataset_size,
        'threshold_suggestions': threshold_suggestions,
        'category_metrics': {
            cat_name: {
                'precision': metrics.get_precision(),
                'recall': metrics.get_recall(),
                'f1': metrics.get_f1(),
                'tp': metrics.tp,
                'fp': metrics.fp,
                'fn': metrics.fn,
                'tn': metrics.tn,
                'suggested_threshold': threshold_suggestions[cat_name],
                'mean_score_positive': float(np.mean(metrics.scores_positive)) if metrics.scores_positive else 0.0,
                'mean_score_negative': float(np.mean(metrics.scores_negative)) if metrics.scores_negative else 0.0
            }
            for cat_name, metrics in category_metrics.items()
        },
        'detailed_results': detailed_results
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_export, f, indent=2, ensure_ascii=False)

    print(f"\n{Colors.GREEN}✅ Resultados guardados en: {output_file}{Colors.END}\n")

    # ===== SQL PARA APLICAR THRESHOLDS =====
    sql_file = os.path.join(output_dir, "apply_thresholds.sql")

    with open(sql_file, 'w', encoding='utf-8') as f:
        f.write("-- Script SQL para aplicar thresholds calibrados\n")
        f.write("-- Ejecutar con: python local_db_tool.py sql --file apply_thresholds.sql\n\n")

        for cat_name, threshold in sorted(threshold_suggestions.items()):
            f.write(f"-- {cat_name}: F1={category_metrics[cat_name].get_f1():.2%}\n")
            f.write(f"UPDATE categories SET confidence_threshold = {threshold:.4f} WHERE name = '{cat_name}';\n\n")

    print(f"{Colors.BLUE}📝 Script SQL generado: {sql_file}{Colors.END}")
    print(f"   Aplica con: python local_db_tool.py sql --file {sql_file}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Calibrar thresholds del sistema multi-label')
    parser.add_argument('--dataset', default=DEFAULT_DATASET_PATH, help='Path al dataset etiquetado (JSON)')
    parser.add_argument('--output', default='calibration_results', help='Directorio de salida')

    args = parser.parse_args()

    # Cargar dataset
    dataset = load_dataset(args.dataset)
    print(f"\n{Colors.GREEN}✅ Dataset cargado: {len(dataset)} imágenes{Colors.END}")

    # Evaluar
    evaluation_results = evaluate_dataset(dataset, args.output)

    # Generar reporte
    generate_report(evaluation_results, args.output)

    print(f"\n{Colors.BOLD}🎯 Siguiente paso:{Colors.END}")
    print(f"   1. Revisa el reporte y casos de fallo")
    print(f"   2. Aplica thresholds sugeridos: python local_db_tool.py sql --file {args.output}/apply_thresholds.sql")
    print(f"   3. Prueba en diagnóstico con nuevas imágenes")
    print(f"   4. Itera: agrega más ejemplos de categorías problemáticas y recalibra\n")


if __name__ == "__main__":
    main()
