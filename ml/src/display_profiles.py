"""Synthetic display identity is never a training/evaluation feature."""
FIRST = 'Amina Brian Faith Kevin Sharon David Mary James Grace Peter Mercy John Esther Daniel Ruth Joseph Sarah Samuel Alice Michael Jane Paul Ann George Naomi Stephen Lucy Victor Rose Eric Lydia Dennis Susan Patrick Hellen Felix Caroline Simon Irene Martin'.split()
LAST = 'Hassan Otieno Wanjiku Mwangi Achieng Kiptoo Njeri Ochieng Kamau Wambui Onyango Mutua Wekesa Chebet Kariuki Muthoni Odhiambo Korir Nyambura Maina Omondi Wairimu Kiplagat Mwende Karanja Njoroge Wafula Wanjala Musyoka Cherono Njuguna Wambua Otiso Mugo Kimani Barasa Wanjohi Kiprotich Anyango Chepkemoi Ndegwa Ouma Muli Wanjiru Kipchoge Atieno Kilonzo Munene Mariga Ndungu'.split()

def make_profiles(model, capability_profiles):
    result={}
    locations=['Nairobi','Mombasa','Kisumu','Nakuru','Eldoret']
    for index, source_id in enumerate(sorted(a['id'] for a in model.agents)):
        totals=model.history.get(source_id,{})
        success=sum(v[0] for v in totals.values()); count=sum(v[1] for v in totals.values())
        result[source_id]={'source_worker_id':source_id,'agent_id':f'AGENT_{index+1:04d}',
            'agent_name':FIRST[index%len(FIRST)]+' '+LAST[index//len(FIRST)],
            'skills':['NetEase capability '+c for c in sorted(capability_profiles.get(source_id,{}))],
            'historical_task_count':count,'historical_success_rate':success/count if count else None,
            'experience_level':'Extensive recorded history' if count>=100 else 'Some recorded history' if count else 'No training history',
            'location':locations[index%len(locations)],'workload':0,'capacity':5,'availability':True,
            'provenance':{'agent_name':'synthetic display identity','location':'synthetic demo',
                'workload':'synthetic initial demo state','capacity':'synthetic demo policy','availability':'synthetic initial demo state',
                'skills':'training participation, not certified competence',
                'historical_task_count':'NetEase training only','historical_success_rate':'NetEase training only',
                'experience_level':'display label derived from training count; not employment tenure'}}
    return result
