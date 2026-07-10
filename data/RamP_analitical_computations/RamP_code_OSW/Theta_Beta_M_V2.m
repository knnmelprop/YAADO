function [sol] = Theta_Beta_M_V2(thetaInf,betaInf,MInf,k,degrad)

% PURPOSE
% Use the Theta-Beta-M relation to obtain the flow deflection angle from
%  the shock wave angle and freestream Mach number

% REFERENCES
% Modern Compressible Flow, Anderson, pg. 136, eqn. 4.17

% INPUTS
% thetaInf : Cone angle to horizontal [deg/rad] 
% betaInf  : Shockwave angle to horizontal [deg/rad]
% MInf     : Freestream Mach number 
% k        : Ratio of specific heats 
% degrad   : Specify whether calculations are in degrees or radians [str]

% OUTPUTS
% sol      : Solution value, depending on what is being solved for

% Convert between degrees and radians if necessary
if (strcmp(degrad,'deg'))
    thetaInf = thetaInf*(pi/180);
    betaInf  = betaInf*(pi/180);
elseif (strcmp(degrad,'rad'))
    % Do nothing, computations are in radians
end

% -------------------- SOLVING FOR: THETA ---------------------------------
if (thetaInf == 0)
    
    % Check against Mach wave angle equation
    if (betaInf <= asin(1/MInf))
        sol = 0;
        return;
    end
    
    % Numerator and denominator
    N = ((MInf*sin(betaInf))^2)-1;
    D = (MInf^2*(k+cos(2*betaInf)))+2;
    
    % Wedge angle from the Theta-Beta-M relation
    theta = atan(2*cot(betaInf)*(N/D));
    
    % Set solution variable based on input deg/rad
    if (strcmp(degrad,'deg'))                                               % If the output is in degrees
        sol = theta*(180/pi);
    elseif (strcmp(degrad,'rad'))                                           % If the output is in radians
        sol = theta;
    end
end

%{ 
----------------- SOLVING FOR: MACH NUMBER ------------------------------
elseif (MInf == 0)
    
    % Find zero of theta-beta-M equation
    myfun = @(t,b,g,M) (2*cot(b)*((((M*sin(b))^2)-1)/...
                        ((M^2*(g+cos(2*b)))+2))) - tan(t);
    t   = thetaInf;                                                         % Given cone angle [rad]
    b   = betaInf;                                                          % Given shock angle [rad]
    g   = k;                                                                % Given ratio of specific heats []
    fun = @(M) myfun(t,b,g,M);                                              % Set given variables in myfun
    M   = fzero(fun,1);                                                     % Solve for M, starting at M = 1
    
    % Set solution variable
    sol = M;                                                                % Set the solution variable
    
% -------------------- SOLVING FOR: BETA ----------------------------------
elseif (betaInf == 0)
    
    % Find zero of theta-beta-M equation
    myfun = @(t,b,g,M) (2*cot(b)*((((M*sin(b))^2)-1)/...
                        ((M^2*(g+cos(2*b)))+2))) - tan(t);
    t   = thetaInf;                                                         % Given cone angle [rad]
    M   = MInf;                                                             % Given Mach number [rad]
    g   = k;                                                              % Given ratio of specific heats []
    fun = @(b) myfun(t,b,g,M);                                              % Set given variables in myfun
    b   = fzero(fun,0.5);
    
    % Set solution variable based on input deg/rad
    if (strcmp(degrad,'deg'))                                               % If the output is in degrees
        sol = b*(180/pi);
    elseif (strcmp(degrad,'rad'))                                           % If the output is in radians
        sol  = b;
    end
    
end
%}
