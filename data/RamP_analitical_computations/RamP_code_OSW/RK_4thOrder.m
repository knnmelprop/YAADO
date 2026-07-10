function [u1, u2] = RK_4thOrder (V1, V2, Tcone, Twave, k)

% Inputs
%V1     = Radial velocity [m/s]
%V2     = Angular velocity [m/s]
%Tcone  = Cone angle [rad/deg]
%Twave  = Wave angle [rad/deg]

h = -0.1;                                                                   % Set the step size
x = Twave:h:Tcone;                                                          % Set the interval of x

A = (k-1)/2;

u1 = zeros(1,length(x));                                                    % u1 = Vr
u2 = zeros(1,length(x));                                                    % u2 = dVr/dVtheta

% Initial conditions
    u1(1) = V1;
    u2(1) = V2;
    t(1)  = 0;
    
% Defining function
    F1 = @(t, u1, u2) u2;
    F2 = @(t, u1, u2) (u1*u2^2-A*(1-u1^2-u2^2)*(2*u1+u2*cot(Twave)))...
                      /(A*(1-u1^2-u2^2) - u2^2);

% Calculation loop

for i=1:(length(x)-1)                                                       
    
    k1 = h*F1(t, u1(i), u2(i));
    m1 = h*F1(t, u1(i), u2(i));
    
    k2 = h*F2(t+0.5*h, u1(i)+0.5*h, u2(i)+0.5*h*k1);
    m2 = h*F2(t+0.5*h, u1(i)+0.5*h, u2(i)+0.5*h*k1);
    
    k3 = h*F1(t+0.5*h, (u1(i)+0.5*h), (u2(i)+0.5*h*k2));
    m3 = h*F2(t+0.5*h, (u1(i)+0.5*h), (u2(i)+0.5*h*k2));
    
    k4 = h*F1(t+h, (u1(i)+h),(u2(i)+k3*h));
    m4 = h*F2(t+h, (u1(i)+h),(u2(i)+k3*h));
 
    % main equation
    u1(i+1) = u1(i) + (1/6)*(k1+2*k2+2*k3+k4)*h;
    u2(i+1) = u2(i) + (1/6)*(m1+2*m2+2*m3+m4)*h;

end
end