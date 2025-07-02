# import plotly.express as px
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
import numpy as np

pre_data = '../data/pre_survey_official.csv'  
post_data = '../data/post_survey_official.csv'

pre_df = pd.read_csv(pre_data, sep=',')
post_df = pd.read_csv(post_data, sep=',')

# # Extract the last number from the code column
post_df['system'] = post_df['Code'].str.extract(r'-(\d+)$').astype(int)

def get_measure_by_condition(df, measure, condition):
    _df = df[df['system'] == condition]
    _df = np.array(_df[measure])
    return _df

non_game_no_gui_stress = get_measure_by_condition(post_df, "Stress_1", 1)
gamified_no_gui_stress = get_measure_by_condition(post_df, "Stress_1", 2)
non_game_gui_stress = get_measure_by_condition(post_df, "Stress_1", 3)
game_gui_stress = get_measure_by_condition(post_df, "Stress_1", 4)
print(non_game_no_gui_stress)


statistic, p_value = stats.friedmanchisquare(non_game_no_gui_stress, gamified_no_gui_stress, non_game_gui_stress, game_gui_stress)

print(statistic)
print(p_value)



# import numpy as np
# from scipy import stats
# from itertools import combinations

# # Example Likert scale data (1-7) for 4 conditions with 20 participants
# np.random.seed(42)  # For reproducibility
# condition1 = np.random.randint(1, 8, 20)  # Likert 1-7
# condition2 = np.random.randint(1, 8, 20)
# condition3 = np.random.randint(1, 8, 20)
# condition4 = np.random.randint(1, 8, 20)

# print(condition1)

# # Prepare data for Friedman test
# data = np.array([condition1, condition2, condition3, condition4]).T

# # Perform Friedman test
# statistic, p_value = stats.friedmanchisquare(condition1, condition2, condition3, condition4)

# print("\nFriedman Test Results:")
# print(f"Chi-square statistic: {statistic:.3f}")
# print(f"p-value: {p_value:.3f}")


# print(f"p-value: {p_value:.3f}")

# if p_value < 0.05:
#     print("\nSignificant main effect found. Performing post-hoc Wilcoxon signed-rank tests with Bonferroni correction")
    
#     # Get all possible pairs of conditions
#     conditions = [condition1, condition2, condition3, condition4]
#     condition_pairs = list(combinations(range(4), 2))
    
#     # Number of comparisons for Bonferroni correction
#     n_comparisons = len(condition_pairs)
    
#     print("\nPairwise Comparisons (Bonferroni-corrected α = 0.05/6 = 0.0083):")
#     for pair in condition_pairs:
#         stat, p = stats.wilcoxon(conditions[pair[0]], conditions[pair[1]])
#         print(f"\nCondition {pair[0]+1} vs Condition {pair[1]+1}:")
#         print(f"W-statistic: {stat:.3f}")
#         print(f"p-value: {p:.3f}")
#         print("Significant" if p < (0.05/n_comparisons) else "Not significant")
# else:
#     print("\nNo significant main effect found. Post-hoc tests not performed.")
