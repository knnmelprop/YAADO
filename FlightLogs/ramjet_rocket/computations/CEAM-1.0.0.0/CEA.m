function [problem,time]=CEA(varargin)

% February 7, 2017
% Version 1.0.0.0
% 
% Program debugged, verified, and validated by
% Chip Kopicz
% ERC
%
% Program Translated from FORTRAN and Constructed in MATLAB by
% Sam Kobliska
% ERC., Jacobs ESSSA
%
%%%%% PROBLEM HP
% x=CEA('problem','hp','equilibrium','o/f',6.0338,'case','CEAM-HP1','p,psia',3126.24,'reactants','fuel','H2(L)','H',2,'wt%',100,'h,cal/mol',-2154,'t(k)',20.17,'oxid','O2(L)','O',2,'wt%',100,'h,cal/mol',-3102,'t(k)',90.18,'output','transport','end','screen');
% x=CEA('reac','oxid','Air','wtfrac',1,'t(k)',700,'fuel','C7H8(L)','wtfrac',0.4,'t(k)',298.15,'fuel','C8H18(L),n-octa','wtfrac',0.6,'t(k)',298.15,'prob','case','Example-3','hp','p(bar)',100,10,1,'o/f',17,'omit','CCN','CNC','C2N2','C2O','C3H4,allene','C3H4,propyne','C3H4,cyclo-','C3','C3H5,allyl','C3H6,propylene','C3H6,cyclo-','C3H3,propargyl','C3H6O','C3H7,n-propyl','C3H7,i-propyl','Jet-A(g)','C3O2','C4','C4H2','C3H8O,2propanol','C4H4,1,3-cyclo-','C4H6,butadiene','C4H6,2butyne','C3H8O,1propanol','C4H8,tr2-butene','C4H8,isobutene','C4H8,cyclo-','C4H6,cyclo','(CH3COOH)2','C4H9,n-butyl','C4H9,i-butyl','C4H8,l-butene','C4H9,s-butyl','C4H9,t-butyl','C4H10,isobutane','C4H8,cis2-buten','C4H10,n-butane','C4N2','C5','C3H8','C5H6,l,3cyclo-','C5H8,cyclo-','C5H10,l-pentene','C10H21,n-decyl','C5H10,cyclo-','C5H11,pentyl','C5H11,t-pentyl','C12H10,biphenyl','C5H12,n-pentane','C5H12,i-pentane','CH3C(CH3)2CH3','C12H9,o-bipheny','C6H6','C6H5OH,phenol','C6H10,cyclo-','C6H2','C6H12,l-hexane','C6H12,cyclo-','C6H13,n-hexyl','C6H5,phenyl','C7H7,benzyl','C7H8','C7H8O,cresol-mx','C6H5O,phenoxy','C7H14,l-heptane','C7H15,n-heptyl','C7H16,n-heptane','C10H8,azulene','C8H8,styrene','C8H10,ethylbenz','C8H16,l-octene','C10H8,napthlene','C8H17,n-octyl','C8H18,isooctane','C8H18,n-octane','C9H19,n-octyl','C7H8(L)','C8H18(L),n-octa','Jet-A(L)','C6H6(L)','H2O(s)','H2O(L)','output','trace',1e-15,'mks','end','screen');
% x=CEA('reac','name','NH4CLO4(I)','wt%',72.06,'t(k)',298.15,'name','CHOS-Binder','C',1,'H',1.86955,'O',0.031256,'S',0.008415,'wt%',18.58,'h,cal/mol',-2999.082,'t(k)',298.15,'name','AL(cr)','wt%',9,'t(k)',298.15,'name','MgO(s)','Mg',1,'O',1,'h,cal/mol',-143703,'wt%',0.2,'t(k)',298.15,'name','H2O(L)','wt%',0.16,'t(k)',298.15,'prob','case','Example-5','hp','p,psi',500,250,125,50,5,'omit','CCN','CNC','C2N2','C2O','C3H4,allene','C3H4,propyne','C3H4,cyclo-','C3','C3H5,allyl','C3H6,propylene','C3H6,cyclo-','C3H3,propargyl','C3H6O','C3H7,n-propyl','C3H7,i-propyl','Jet-A(g)','C3O2','C4','C4H2','C3H8O,2propanol','C4H4,1,3-cyclo-','C4H6,butadiene','C4H6,2butyne','C3H8O,1propanol','C4H8,tr2-butene','C4H8,isobutene','C4H8,cyclo-','C4H6,cyclo','(CH3COOH)2','C4H9,n-butyl','C4H9,i-butyl','C4H8,l-butene','C4H9,s-butyl','C4H9,t-butyl','C4H10,isobutane','C4H8,cis2-buten','C4H10,n-butane','C4N2','C5','C3H8','C5H6,l,3cyclo-','C5H8,cyclo-','C5H10,l-pentene','C10H21,n-decyl','C5H10,cyclo-','C5H11,pentyl','C5H11,t-pentyl','C12H10,biphenyl','C5H12,n-pentane','C5H12,i-pentane','CH3C(CH3)2CH3','C12H9,o-bipheny','C6H6','C6H5OH,phenol','C6H10,cyclo-','C6H2','C6H12,l-hexane','C6H12,cyclo-','C6H13,n-hexyl','C6H5,phenyl','C7H7,benzyl','C7H8','C7H8O,cresol-mx','C6H5O,phenoxy','C7H14,l-heptane','C7H15,n-heptyl','C7H16,n-heptane','C10H8,azulene','C8H8,styrene','C8H10,ethylbenz','C8H16,l-octene','C10H8,napthlene','C8H17,n-octyl','C8H18,isooctane','C8H18,n-octane','C9H19,n-octyl','C7H8(L)','C8H18(L),n-octa','Jet-A(L)','C6H6(L)','H2O(s)','H2O(L)','output','calories','end','screen');
%
%%%%% PROBLEM TP
% x=CEA('problem','tp','equilibrium','o/f',6.0:.2:7.0,'case','CEAM-TP1','p,psi',1000.,2000,'t,R',5500:500:6500,'outp','transport','reactants','fuel','H2','wt%',100.,'t(k)',298.15,'oxid','O2','wt%',100,'t(k)',298.15,'end','screen');
% x=CEA('problem','case','Example-1','tp','p(atm)',1,0.1,0.01,'t(k)',3000,2000,'r.eq.ratio',1,1.5,'reac','fuel','H2','moles',1,'oxid','Air','moles',1,'only','Ar','C','CO','CO2','H','H2','H2O','HO2','HNO2','HNO3','N','NH','NO','N2','N2O3','O','O2','OH','O3','output','calories','end','screen');
% x=CEA('reactants','name','H2(L)','H',2,'moles',100,'h,J/mol',-9012,'name','O2(L)','O',2,'moles',60,'h,J/mol',-12979,'prob','tp','case','Example-14','p,atm',0.05,'t(k)',1000,500,350,305,304.3,304.2,304,300,'output','debug',5,'end','screen');
%
%%%%% PROBLEM SP
% x=CEA('reactants','fuel','H2(L)','H',2,'wt%',100.0,'oxid','O2(L)','O',2,'wt%',100.0,'only','H','H2','H2O','O','OH','O2','problem','sp','case','CEAM-SP1','o/f',6.00,'p,psi',628.960,'s/r',2.17959,'output','short','massf','end');
%
%%%%% PROBLEM ROCKET
% x=CEA('problem','rocket','equilibrium','fac','acat',3,'o/f',2.34,2.5,'case','CEAM-rocket1','p(psi)',633,800,'subsonic(ae/at)',2.59,1.01,'supsonic(ae/at)',1.01,15.0,30.0,'reactants','fuel','RP-1(L)','C',1,'H',1.9423,'wt%',100,'h,cal/mol',-5430,'t(k)',300.0,'oxid','O2(L)','O',2,'wt%',100,'h,cal/mol',-3032,'t(k)',94.44,'output','transport','mks','end','screen');
% x=CEA('reactants','name','HEHN','wt',44.500,'C',2,'H',9,'N',3,'O',4,'h,kcal/mol',-98.000,'rho,g/cc',1.428,'name','HAN','wt',41.830,'H',4,'N',2,'O',4,'h,kcal/mol',-95.300,'rho,g/cc',1.090,'name','AN','wt',02.225,'H',4,'N',2,'O',3,'h,kcal/mol',-87.380,'rho,g/cc',1.725,'name','DIPY','wt',00.445,'C',10,'H',8,'N',2,'h,kcal/mol',44.478,'rho,g/cc',1.326,'name','Water','wt',11.000,'H',2,'O',1,'h,kcal/mol',-68.313,'rho,g/cc',1.000,'problem','rocket','frozen','p,psia',300,'sup,ae/at',10.0000,'output','massf','transport','end','screen');
% x=CEA('problem','rocket','equilibrium','o/f',5.55157,'case','Example-8','p,bar',53.3172,'subar',1.58,'pi/p',10,100,1000,'supar',25,50,75,'reactants','fuel','H2(L)','wt%',100,'t(k)',20.27,'oxid','O2(L)','wt%',100,'t(k)',90.17,'output','mks','end','screen');
% x=CEA('problem','rocket','equilibrium','o/f',5.55157,'case','Example-9','p,bar',53.3172,'fac','acat',1.58,'pi/p',10,100,1000,'supar',25:25:75,'reactants','fuel','H2(L)','wt%',100,'t(k)',20.27,'oxid','O2(L)','wt%',100,'t(k)',90.17,'output','mks','end','screen');
% x=CEA('problem','rocket','equilibrium','o/f',5.55157,'case','Example-10','p,bar',53.3172,'fac','ma,kg/m^2',1333.9,'pi/p',10,100,1000,'supar',25:25:75,'reactants','fuel','H2(L)','t(k)',20.27,'oxid','O2(L)','t(k)',90.17,'output','mks','short','end','screen');
% x=CEA('reactants','fuel','CH6N2(L)','rho,g/cc',0.874,'oxid','N2O4(L)','rho,g/cc',1.431,'problem','rocket','equilibrium','case','Example-12','p,psi',1000,'pi/p',68.0457,'o/f',2.5,'eql','froz','nfz',2,'supar',5,10,25,50,75,100,150,200,'only','C','CO','CO2','H','HNO','HNO2','HO2','H2','H2O','H2O2','N','NO','NO2','N2','N2O','O','OH','O2','HCO','NH','CH4','NH2','NH3','H2O(L)','C(gr)','output','mks','end','screen');
% x=CEA('reac','name','SR_AL','AL',1.00,'h,cal/mol',0.,'wt%',18.0,'t(k)',298.15,'name','AM_PERCL','N',1,'H',4,'O',4,'CL',1,'wt%',68.00,'h,cal/mol',-70700.,'t(k)',298.15,'name','Dio_Adi','C',22.,'H',42.,'O',4.,'wt%',2.0,'h,cal/mol',-296000.,'t(k)',298.15,'name','HTPB','C',7.332,'H',10.962,'O',0.058,'h,cal/mol',-250.,'wt%',11.00,'t(k)',298.15,'name','HX-752','C',14.,'H',16.,'N',2.0,'O',2.,'wt%',0.20,'h,cal/mol',-61000.,'t(k)',298.15,'name','stabilizer','C',38.,'H',66.,'N',2.,'wt%',0.10,'h,cal/mol',-206300.,'t(k)',298.15,'prob','rkt','p,psia',1000,'outp','massf','transport','mks','end','screen');
% x=CEA('problem','rocket','equilibrium','case','Example-11','p,psi',1000,'ions','pi/p',68.0457,'subar',10,'supar',10,20,100,'reactants','fuel','Li(Cr)','moles',1,'t(k)',298.15,'oxid','F2(L)','moles',0.5556,'t(k)',85.02,'output','mks','end','screen');
% x=CEA('reactants','fuel','N2H4(L)','wt%',80,'t(k)',298.15,'fuel','Be(a)','wt%',20,'t(k)',298.15,'oxid','H2O2(L)','wt%',100,'t(k)',298.15,'prob','rocket','case','Example-13','p,psia',3000,'pi/p',3,10,30,300,'equilibrium','%fuel',67,'insert','BeO(L)','output','trace',1e-10,'calories','end','screen');
%
% [x time]=CEA('problem','rkt','eql','o/f',6,'case','Example','p,psia',1000,'subson',2,'supson',30,'pi/p',1.1,10,'reactants','fuel','H2(L)','H',2,'wt%',100,'h,cal/mol',-2100, 't(k)',20.17,'oxid','O2(L)','O',2,'wt%',100,'h,cal/mol',-3100,'t(k)',90.18,'omit','O3','output','eng','transport','trace',1e-10,'end','screen');
%
%%%%% PROBLEM SV
% No example
%
%%%%% PROBLEM TV
%  x=CEA('reac','fuel','H2','wt%',100,'oxid','Air','wt%',100,'problem','case','Example-2','phi,eq.ratio',1,'tv','t(k)',3000,'rho,g/cc',9.186e-5,8.0877e-6,6.6054e-7,'only','Ar','C','CO','CO2','H','H2','H2O','HO2','HNO2','HNO3','N','NH','NO','N2','N2O3','O','O2','OH','O3','output','transport','calories','end','screen');
%
%%%%% PROBLEM UV
% x=CEA('reac','oxid','Air','wtfrac',1,'t(k)',700,'fuel','C7H8(L)','wtfrac',0.4,'t(k)',298.15,'fuel','C8H18(L),n-octa','wtfrac',0.6,'t(k)',298.15,'prob','case','Example-4','uv','o/f',17,'u/r',-45.1343,'rho,kg/m^3',14.428,'omit','CCN','CNC','C2N2','C2O','C3H4,allene','C3H4,propyne','C3H4,cyclo-','C3','C3H5,allyl','C3H6,propylene','C3H6,cyclo-','C3H3,propargyl','C3H6O','C3H7,n-propyl','C3H7,i-propyl','Jet-A(g)','C3O2','C4','C4H2','C3H8O,2propanol','C4H4,1,3-cyclo-','C4H6,butadiene','C4H6,2butyne','C3H8O,1propanol','C4H8,tr2-butene','C4H8,isobutene','C4H8,cyclo-','C4H6,cyclo','(CH3COOH)2','C4H9,n-butyl','C4H9,i-butyl','C4H8,l-butene','C4H9,s-butyl','C4H9,t-butyl','C4H10,isobutane','C4H8,cis2-buten','C4H10,n-butane','C4N2','C5','C3H8','C5H6,l,3cyclo-','C5H8,cyclo-','C5H10,l-pentene','C10H21,n-decyl','C5H10,cyclo-','C5H11,pentyl','C5H11,t-pentyl','C12H10,biphenyl','C5H12,n-pentane','C5H12,i-pentane','CH3C(CH3)2CH3','C12H9,o-bipheny','C6H6','C6H5OH,phenol','C6H10,cyclo-','C6H2','C6H12,l-hexane','C6H12,cyclo-','C6H13,n-hexyl','C6H5,phenyl','C7H7,benzyl','C7H8','C7H8,cresol-mx','C6H5O,phenoxy','C7H14,l-heptane','C7H15,n-heptyl','C7H16,n-heptane','C10H8,azulene','C8H8,atyrene','C8H10,ethylbenz','C8H16,l-octene','C10H8,napthlene','C8H17,n-octyl','C8H18,isooctane','C8H18,n-octane','C9H19,n-octyl','C7H8(L)','C8H18(L),n-octa','Jet-A(L)','C6H6(L)','H2O(s)','H2O(L)','output','mks','trace',1e-15,'end','screen');
%
%%%%% SHOCK
% x=CEA('reac','name','H2','moles',2.0,'name','O2','moles',1.0,'prob','sh','inc','fr','eql','u1',2837.1,'t',300.,'p,atm',1.0,'output','transport','end','screen');
% x=CEA('reac','name','H2','moles',0.050,'t(k)',300.0,'name','O2','moles',0.050,'t(k)',300.0,'name','Ar','moles',0.900,'t(k)',300.0,'problem','case','Example-7','p,mmhg',10,20,'shock','u1,m/s',1000,1100,1200,1250,1300,1350,'incd','froz','eql','end','screen');
%
%%%%% DETN
% x=CEA('reac','name','H2','moles',2.0,'name','O2','moles',1.0,'prob','det','t,k',300.,'p,atm',1.0,'output','transport','end','screen');
% x=CEA('reac','name','C2H4','moles',1.0000,'name','O2','moles',3.0000,'prob','det','t,k',298.,'p,atm',1.0,'output','transport','end','screen');
% x=CEA('reac','oxid','O2','wt%',100,'t(k)',298.15,'fuel','H2','wt%',100,'t(k)',298.15,'problem','det','case','Example-6','t(k)',298.15,500,'r,e',1,'p,bar',1,20,'output','trace',1e-5,'calories','transport','end','screen');
%
% Known Problems
%   There are currently no known problems.


end