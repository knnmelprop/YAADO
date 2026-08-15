%% This code is ment to prove the co2 bags concept %%
m = 88e-3; %[kg] mass of the CO2 in the container
n = 2; %[-] number of containters
p = 1006e2; %[Pa]
R = 188.92; %[kJ/kg] carbon dioxide gas individual gas constant
T = 273.15+20.4; %[K] surounding's temp
%T = 273.15+3;

mt = m*n;

V = (mt*R*T)/p; %[m^3] minimal volume of the gas bag
V_liters = V*1e3;
V_per_bottle_liters = V_liters/n;
%{
increment = 0.15;
for i = 1:20
    increment = 0.15 + increment;
    width(i) = increment;
end
%}