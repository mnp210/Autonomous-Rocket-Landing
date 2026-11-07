import json

data = json.load(open('experiments/benchmark/production_benchmark_summary.json', encoding='utf-8'))
ps = list(data['paradigm_statistical_analyses'].keys())
conds = list(data['paradigm_statistical_analyses'][ps[0]]['conditions'].keys())

print('Condition'.ljust(25) + ' | ' + ' | '.join([p.ljust(20) for p in ps]))
print('-' * 115)
for c in conds:
    cat = data['paradigm_statistical_analyses'][ps[0]]['conditions'][c]['category']
    c_label = f"[{'ID' if cat == 'in_distribution' else 'OOD'}] {c}"
    row = [f"{data['paradigm_statistical_analyses'][p]['conditions'][c]['success_rate_ci']['mean']*100:5.1f}% (+-{data['paradigm_statistical_analyses'][p]['conditions'][c]['success_rate_ci']['margin_of_error']*100:4.1f}%)".ljust(20) for p in ps]
    print(c_label.ljust(25) + ' | ' + ' | '.join(row))

print('\n' + '=' * 115)
print('OVERALL SUMMARY'.ljust(25) + ' | ' + ' | '.join([p.ljust(20) for p in ps]))
print('-' * 115)
id_row = [f"{data['paradigm_statistical_analyses'][p]['in_distribution']['success_rate_ci']['mean']*100:5.1f}% (+-{data['paradigm_statistical_analyses'][p]['in_distribution']['success_rate_ci']['margin_of_error']*100:4.1f}%)".ljust(20) for p in ps]
print('In-Distribution Mean'.ljust(25) + ' | ' + ' | '.join(id_row))

ood_row = [f"{data['paradigm_statistical_analyses'][p]['out_of_distribution']['success_rate_ci']['mean']*100:5.1f}% (+-{data['paradigm_statistical_analyses'][p]['out_of_distribution']['success_rate_ci']['margin_of_error']*100:4.1f}%)".ljust(20) for p in ps]
print('Out-of-Distribution Mean'.ljust(25) + ' | ' + ' | '.join(ood_row))

gap_row = [f"{(data['paradigm_statistical_analyses'][p]['in_distribution']['success_rate_ci']['mean'] - data['paradigm_statistical_analyses'][p]['out_of_distribution']['success_rate_ci']['mean'])*100:5.1f}%".ljust(20) for p in ps]
print('Generalization Gap'.ljust(25) + ' | ' + ' | '.join(gap_row))

r_row = [f"{data['paradigm_statistical_analyses'][p]['in_distribution']['mean_reward_ci']['mean']:6.1f} (+-{data['paradigm_statistical_analyses'][p]['in_distribution']['mean_reward_ci']['margin_of_error']:5.1f})".ljust(20) for p in ps]
print('ID Mean Reward'.ljust(25) + ' | ' + ' | '.join(r_row))
