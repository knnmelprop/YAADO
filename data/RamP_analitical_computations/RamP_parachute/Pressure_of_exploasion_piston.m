%% Explosion in the piston %%
%% Constants
p_i = 1e5; %[Pa] initial pressure
T_i = 273.15+21; %[K] initial temp
rho_i = 1.225; %[Pa] initial density
Cv = 0.718e3; %[J/(kg*K)] specific heat at const. volume
d = 14e-3; %[m] diameter of the piston
R = 287; %[J/(kg*K)] individual gas const.

h_i = 20e-3; %[m] initial height of the piston
E = 500; %[J] explosion energy
%% Calculations
V_i = d^2*0.25*pi*h_i; %[m^3] 
m = rho_i*V_i; %[kg] mass of the air
p_f = p_i*(E/(Cv*T_i*rho_i*V_i)+1); %[Pa] Pressure in the chamber at initial state
pf_bar = p_f*1e-5; %[bar] the same but in bar
T_f = (p_f/p_i)*T_i; %[K] temp in the chamber
T_f_klepieron = (p_f*V_i)/(m*R); %[K] temp in the chamber calc by klapeiron
