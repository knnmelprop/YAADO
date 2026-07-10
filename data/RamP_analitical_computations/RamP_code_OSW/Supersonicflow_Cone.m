function [M2, Mn1, Mn2 rho2_rho1, P2_P1, T2_T1, theta_c_d] = Supersonicflow_Cone (s, M1, k)
% Case study
% Conical flow : Supersonic flow past an un-yawed cone

% Assuming the gas to be invisced and calorically perfect

% Defining variables and assigning values
%s = 60; %OSW angleM
theta_s_r = deg2rad(61);                                                    % Conical shock angle [rad]
M1 = 2;                                                                   % Free stream Mach number
k = 1.4;                                                                    % Ratio of Specific heats

% Cone Angle Calculated from Theta-Beta-M function-file
    [theta_c_r] = Theta_Beta_M_V2(0,theta_s_r,M1,k,'rad');                      
    
% Using oblique shock relations to get M behind shock
    Mn1 = M1*sin(theta_s_r);                                                % Normal Mach number pre-shock, Eqn. 4.7 (pg. 135)
    Mn2 = sqrt((1 + ((k-1)/2)*Mn1^2)/((k*Mn1^2) - ((k-1)/2)));              % Normal Mach number post-shock, Eqn. 3.51 (pg. 89)
    M2  = Mn2/(sin(theta_s_r-theta_c_r));                                   % Post-shock Mach number, Eqn. 4.12 (pg. 135)
    
% Initial conditions
    V      = ((2/((k-1)*M2^2))+1)^(-1/2);                                   % Total velocity    [m/s]
    Vtheta = -V*(sin(theta_s_r-theta_c_r));                                 % Angular velocity  [m/s]
    Vr     = V*(cos(theta_s_r-theta_c_r));                                  % Radial velocity   [m/s]
    
%Theta range and initial conditions of Vr and Vr'
    thetarange = [theta_s_r; 1e-10];                                        % Integrate from shock angle to ~ 0 degrees
    V_init    = [Vr; Vtheta];                                               % Initial values for Vr and dVr/dTheta (Vtheta)
    
    
% Solution from RK method function defined at the bottom of the script
    [sol1, sol2] = RK_4thOrder(Vr, Vtheta, theta_c_r, theta_s_r, k);
   
    options = odeset('Events',@EVENTS, 'Reltol', 2.22045e-14);
    sol     = ode15s(@TM_Equations,thetarange,V_init,options,k);            
    
% If the method worked, calculate angle and Mach number at the cone
    [n,m]  = size(sol.y);                                                   % Get the size of the solution array
    if (n > 0 && m > 0 && isempty(sol.ie) ~= 1)                             % If the solution converged
        theta_c_r = sol.xe;                                                 % Final cone angle [rad]
        theta_c_d = theta_c_r.*(180/pi);                                    % Final cone angle [deg]
        Vc2       = sol.ye(1)^2 + sol.ye(2)^2;                              % Total velocity squared [m/s]^2
        Mc        = ((1.0/Vc2-1)*(k-1)/2)^-0.5;                             % Mach number at cone surface

    else
        % Indicating in the command window that no solution was found
        %fprintf('No cone angle solution found!\n');
        M2 = 0;                                                             % if no solution, 0 is assinged  
        rho2_rho1 = 0;                                                      % if no solution, 0 is assinged  
        P2_P1 = 0;                                                          % if no solution, 0 is assinged  
        T2_T1 = 0;                                                          % if no solution, 0 is assinged  
        theta_c_d = 0;                                                      % if no solution, 0 is assinged
        warning off;
    end
    
% Solution arrays for shock layer
    sol_V2    = (sol.y(1,:).^2 + sol.y(2,:).^2)';                           % Total velocity squared
    sol_Mc    = ((1./sol_V2-1).*(k-1)/2).^(-0.5);                           % Cone surface Mach number
    sol_X_rad = sol.x';                                                     % Integration angles [rad]
    sol_X_deg = (sol.x').*(180/pi);                                         % Integration angles [deg]
    
    deltheta = theta_s_r:-0.1*pi/180:theta_c_r;                             % Variation of theta_s_r from 29 deg to 0 deg 
                                                                            % in steps of -0.1 degrees
% Results
    %fprintf('Solutions for Case study - \n\nInputs:\nMinf = %0.3f, k = %0.3f, theta_s = %0.3f degrees\n\nSolution:\n', M1, k, 180*theta_s_r/pi);
    %fprintf('M2 = %0.4f\n', M2);
    %fprintf('Mc = %0.3f\n', Mc);
    %fprintf('theta_c = %0.3f degrees\n', theta_c_d);
   
% Oblique Shock Relations
    rho2_rho1 = (k+1)*Mn1^2/((k-1)*Mn1^2+2);                                % Eqn. 4.8 (pg. 135)
    P2_P1     = 1 + 2*k*(Mn1^2-1)/(k+1);                                    % Eqn. 4.9 (pg. 135)
    T2_T1     = P2_P1/rho2_rho1;                                            % Eqn. 4.11 (pg. 135)
    
    
% Stagnation point relation derived from Isoentropic relations
% From station c to stagnation, M = Mc
    T02_T     = 1+(k-1)*sol_Mc.^2/2;                                        % Eqn. 3.29 (pg. 80)
    P02_P     = (1+(k-1)*sol_Mc.^2/2).^(k/(k-1));                           % Eqn. 3.30 (pg. 80)
    rho02_rho = (1+(k-1)*sol_Mc.^2/2).^(1/(k-1));                           % Eqn. 3.31 (pg. 80)
    
% From station 2 to stagnation, M = M2
    T02_T2     = 1+(k-1)*M2^2/2;                                            % Eqn. 3.29 (pg. 80)
    P02_P2     = (1+(k-1)*M2^2/2)^(k/(k-1));                                % Eqn. 3.30 (pg. 80)
    rho02_rho2 = (1+(k-1)*M2^2/2)^(1/(k-1));                                % Eqn. 3.31 (pg. 80)
    
% Calculating required variables using the above variables
    P_P1 = P02_P2*P2_P1./P02_P;
    T_T1 = T02_T2*T2_T1./T02_T;
    rho_rho1 = rho02_rho2*rho2_rho1./rho02_rho;
    
    
 %{
    figure(1);
    plot(sol.x*180/pi, sol_Mc, 'r');
    legend('Mach number', 'FontWeight', 'bold', 'FontSize', 14, 'Location', 'best');
    xlabel('Theta (degrees)', 'FontSize', 14, 'FontWeight', 'bold');
    xlim([8 32]);xticks(10:2:30);
    ylim([1.75 2.25]);yticks(1.75:0.05:2.25);
    set(gca, 'xdir', 'reverse');
    
    figure(2);
    plot(sol.x*180/pi, P_P1, 'b');
    legend('P/P1', 'FontWeight', 'bold', 'FontSize', 14, 'Location', 'best');
    xlabel('Theta (degrees)', 'FontSize', 14, 'FontWeight', 'bold');
    xlim([8 32]);xticks(10:2:30);
    set(gca, 'xdir', 'reverse');
    
    figure(3);
    plot(sol.x*180/pi, T_T1, 'k');
    legend('T/T1', 'FontWeight', 'bold', 'FontSize', 14, 'Location', 'best');
    xlabel('Theta (degrees)', 'FontSize', 14, 'FontWeight', 'bold');
    xlim([8 32]);xticks(10:2:30);
    set(gca, 'xdir', 'reverse');
    
    figure(4);
    plot(sol.x*180/pi, rho_rho1, 'g');    
    legend('{\rho}/{\rho1}', 'FontWeight', 'bold', 'FontSize', 14, 'Location', 'best');
    xlabel('Theta (degrees)', 'FontSize', 14, 'FontWeight', 'bold');
    xlim([8 32]);xticks(10:2:30);
    ylim([1.1 1.3]);
    set(gca, 'xdir', 'reverse');
    
    figure(5);
    plot(sol.x*180/pi, sol.y(2,:), 'm');
    legend('Vtheta/Vmax', 'FontWeight', 'bold', 'FontSize', 14, 'Location', 'best');
    xlabel('Theta (degrees)', 'FontSize', 14, 'FontWeight', 'bold');
    xlim([8 32]);xticks(10:2:30);
    set(gca, 'xdir', 'reverse');
 %}

    
% Here Vtheta is considered as velocity and not the speed
% If speed plot is required apply mod function to sol.y(2,:)

% Ranga Kutta method code 
function [u1, u2] = RK_4thOrder (V1, V2, Tcone, Twave, k)

% Inputs
%V1     = Radial velocity [m/s]
%V2     = Angular velocity [m/s]
%Tcone  = Cone angle [rad/deg]
%Twave  = Wave angle [rad/deg]

h = -0.1*pi/180;                                                                   % Set the step size
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

end %end of function Supersonicflow_Cone