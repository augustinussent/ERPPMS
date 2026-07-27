from hotel_pms.production_gate_rules import gate_status,money_variance,summarize_checks,threshold_status

def test_money_variance(): assert money_variance('100.00','99.25')==money_variance('.75',0)
def test_threshold(): assert threshold_status(5,10)=='Passed' and threshold_status(9,10)=='Warning' and threshold_status(11,10)=='Failed'
def test_blocker(): assert summarize_checks([{'mandatory':1,'status':'Pending'}])['blockers']==1
def test_ready(): assert gate_status([{'mandatory':1,'status':'Passed'}],[{'status':'Pending'}])=='Ready for Sign-off'
def test_approved(): assert gate_status([{'mandatory':1,'status':'Passed'}],[{'status':'Approved'}])=='Approved'
def test_rejected(): assert gate_status([{'mandatory':1,'status':'Passed'}],[{'status':'Rejected'}])=='Rejected'
