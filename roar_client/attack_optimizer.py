from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga2 import NSGA2
import numpy as np

class RoarOptimizationProblem(ElementwiseProblem):
    def __init__(self):
        # הגדרת המשתנים (למשל: אחוז השינוי בטקסט וזמן ההמתנה)
        super().__init__(n_var=2, 
                         n_obj=2, # יעד 1: מקסימום שינוי טקסט, יעד 2: מינימום זיהוי
                         xl=np.array([0.01, 0.1]), # גבולות תחתונים
                         xu=np.array([0.5, 5.0]))   # גבולות עליונים

    def _evaluate(self, x, out, *args, **kwargs):
        perturbation_level = x[0]
        delay = x[1]
        
        # כאן תבוא האינטגרציה עם הקוד של אפרת:
        # 1. קריאה ל-text_perturbation_tool עם הפרמטרים מ-x
        # 2. קבלת ה-Threshold מה-roar_server
        
        # דוגמה ליעדים (Objectives):
        f1 = -1 * perturbation_level  # אנחנו רוצים למקסם שינוי (לכן מינוס)
        f2 = self.get_server_detection_risk() # פונקציה שתמשוך נתונים מהשרת
        
        out["F"] = [f1, f2]

    def get_server_detection_risk(self):
        # כאן תממשו מחר בזום את המשיכה מהשרת
        return 0.5
